import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "calibration-ui-prtouch-bed-mesh-v2"
MANIFEST = PACKAGE / "deployment-manifest.json"
CONTRACT = PACKAGE / "calibration-ui-prtouch-bed-mesh-v2-contract.json"
COMPONENT = PACKAGE / "k1_control_probe_count.py"
DEPLOYER = ROOT / "scripts" / "deploy-k1-control-calibration-ui-prtouch-bed-mesh-v2.ps1"


def load_component():
    spec = importlib.util.spec_from_file_location("k1_control_probe_count_v2", COMPONENT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeKlippyApis:
    def __init__(self):
        self.loaded = ((6, 6), "lagrange")

    async def query_objects(self, objects):
        if objects != {"configfile": None}:
            raise AssertionError(objects)
        return {
            "configfile": {
                "settings": {
                    "bed_mesh": {
                        "probe_count": list(self.loaded[0]),
                        "algorithm": self.loaded[1],
                    }
                }
            }
        }


class FakeBackend:
    def __init__(self, config_file, module):
        self.config_file = config_file
        self.module = module
        self.klippy_apis = FakeKlippyApis()
        self.commands = []
        self.status = {
            "print_stats": {"state": "standby", "filename": ""},
            "extruder": {"target": 0},
            "heater_bed": {"target": 0},
            "gcode_macro KCTRL_STATE": {
                "ready": 1,
                "session_active": 0,
                "low_moves_armed": 0,
            },
            "gcode_macro KCTRL_CAL_PATH_STATE": {
                "phase": "committed",
                "motion_armed": 0,
            },
        }

    async def query_status(self):
        return self.status

    async def run_gcode(self, script, disconnect_ok=False):
        self.commands.append((script, disconnect_ok))
        if script == "RESTART":
            file_config = self.module.ProbeCountFile(self.config_file).read()
            self.klippy_apis.loaded = self.module.ProbeCountFile._effective(file_config)
        return "ok"

    async def update_mesh(self, matrix):
        return matrix

    async def wait_klippy_ready(self, timeout):
        return None


class PrtouchBedMeshV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_component()

    def test_contract_records_xs3002_and_the_exact_atomic_pair(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(
            contract["contract_id"],
            "G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-BED-MESH-V2",
        )
        self.assertEqual(contract["observed_failure"]["screen_code"], "XS3002")
        self.assertEqual(contract["observed_failure"]["mesh_measurements"], 0)
        self.assertEqual(
            contract["runtime"]["atomic_fields"],
            ["bed_mesh.probe_count", "bed_mesh.algorithm"],
        )
        self.assertIn(
            {"probe_count": [9, 9], "algorithm": "bicubic"},
            contract["runtime"]["supported_pairs"],
        )
        self.assertIn(
            {"probe_count": [9, 9], "algorithm": "lagrange"},
            contract["runtime"]["forbidden_pairs"],
        )

    def test_manifest_pins_exact_upgrade_baseline_and_payload(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["baseline"]["component_sha256"],
            "72e2010c06afe58d78416fca1c65e746c805568c90cf2ac13d1f6196b46f09ca",
        )
        self.assertEqual(manifest["baseline"]["loaded_probe_count"], [6, 6])
        self.assertEqual(manifest["baseline"]["loaded_algorithm"], "lagrange")
        self.assertFalse(manifest["baseline"]["algorithm_line_present"])
        self.assertEqual(len(manifest["files"]), 1)
        self.assertEqual(
            hashlib.sha256(COMPONENT.read_bytes()).hexdigest(),
            manifest["files"][0]["sha256"],
        )
        self.assertEqual(
            hashlib.sha256(CONTRACT.read_bytes()).hexdigest(),
            manifest["contract"]["sha256"],
        )
        self.assertEqual(
            hashlib.sha256(DEPLOYER.read_bytes()).hexdigest(),
            manifest["deployer"]["sha256"],
        )

    def test_deployer_replaces_only_the_component_and_rolls_it_back_exactly(self):
        source = DEPLOYER.read_text(encoding="utf-8")
        self.assertIn("component_sha256", source)
        self.assertIn("k1_control_probe_count.py.before", source)
        self.assertIn("Invoke-ExactRollback", source)
        self.assertIn("S56k1_control_moonraker", source)
        self.assertIn("algorithm: bicubic", source)
        self.assertNotIn("moonraker.conf.before", source)
        for forbidden in ("KCTRL_MESH_CALIBRATE", "M104", "M140", "G28"):
            self.assertNotIn(forbidden, source)

    def test_component_verifies_loaded_count_and_algorithm(self):
        source = COMPONENT.read_text(encoding="utf-8")
        self.assertIn('algorithm = str(bed_mesh.get("algorithm", "")).lower()', source)
        self.assertIn('target_algorithm != "bicubic"', source)
        self.assertIn("self.config.write(previous)", source)
        self.assertIn("ProbeCountFile._effective(previous)", source)

    def test_implicit_lagrange_is_preserved_exactly_after_bicubic_round_trip(self):
        source = (
            b"[include helper.cfg]\n"
            b"[bed_mesh]\n"
            b"speed: 150\n"
            b"probe_count: 6,6\n"
            b"fade_start: 5.0\n\n"
            b"#*# [bed_mesh saved]\n"
            b"#*# points = 0,0\n"
        )
        rewritten, previous = self.module.ProbeCountFile._rewrite(
            source, ((9, 9), "bicubic")
        )
        self.assertEqual(previous, ((6, 6), None))
        self.assertIn(b"probe_count: 9,9\nalgorithm: bicubic\n", rewritten)
        restored, changed = self.module.ProbeCountFile._rewrite(rewritten, previous)
        self.assertEqual(changed, ((9, 9), "bicubic"))
        self.assertEqual(restored, source)

    def test_file_read_distinguishes_implicit_from_explicit_lagrange(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "printer.cfg"
            path.write_bytes(b"[bed_mesh]\nprobe_count: 6,6\n")
            config = self.module.ProbeCountFile(path).read()
            self.assertEqual(config, ((6, 6), None))
            self.assertEqual(
                self.module.ProbeCountFile._effective(config),
                ((6, 6), "lagrange"),
            )


class PrtouchBedMeshV2BackendTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_component()

    async def test_runtime_round_trip_restores_implicit_lagrange_bytes_exactly(self):
        source = b"[bed_mesh]\nspeed: 150\nprobe_count: 6,6\nfade_start: 5.0\n"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            printer = root / "printer.cfg"
            backup_root = root / "backups"
            campaign_id = "campaign-implicit-lagrange"
            campaign_root = backup_root / campaign_id
            campaign_root.mkdir(parents=True)
            printer.write_bytes(source)
            backup = campaign_root / "printer.cfg.before"
            backup.write_bytes(source)
            orchestrator = types.SimpleNamespace(
                backups=types.SimpleNamespace(
                    printer_config=printer,
                    backup_root=backup_root,
                ),
                state={
                    "phase": "preparing",
                    "campaign_id": campaign_id,
                    "config": {
                        "x_count": 9,
                        "y_count": 9,
                        "algorithm": "bicubic",
                    },
                    "backup": {
                        "root": str(campaign_root),
                        "printer_cfg_sha256": hashlib.sha256(source).hexdigest(),
                    },
                },
            )
            backend = FakeBackend(printer, self.module)
            wrapped = self.module.ProbeCountAwareBackend(backend, orchestrator)

            await wrapped.run_gcode("BED_MESH_CLEAR")
            self.assertEqual(backend.klippy_apis.loaded, ((9, 9), "bicubic"))
            self.assertIn(b"probe_count: 9,9\nalgorithm: bicubic\n", printer.read_bytes())

            orchestrator.state["phase"] = "mesh_ready"
            await wrapped.run_gcode("TURN_OFF_HEATERS")
            self.assertEqual(printer.read_bytes(), source)
            self.assertEqual(backend.klippy_apis.loaded, ((6, 6), "lagrange"))
            self.assertFalse(wrapped.changed)


if __name__ == "__main__":
    unittest.main()
