import asyncio
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "calibration-ui-prtouch-matrix-v1"
COMPONENT = PACKAGE / "k1_control_probe_count.py"
CONTRACT = PACKAGE / "calibration-ui-prtouch-matrix-contract.json"
MANIFEST = PACKAGE / "deployment-manifest.json"
DEPLOYER = ROOT / "scripts" / "deploy-k1-control-calibration-ui-prtouch-matrix-v1.ps1"


def load_component():
    spec = importlib.util.spec_from_file_location("k1_control_probe_count", COMPONENT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeKlippyApis:
    def __init__(self, config_file, module):
        self.config_file = config_file
        self.module = module
        self.loaded = ((6, 6), "lagrange")

    async def query_objects(self, objects):
        self.assert_configfile_request(objects)
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

    @staticmethod
    def assert_configfile_request(objects):
        if objects != {"configfile": None}:
            raise AssertionError(objects)


class FakeBackend:
    def __init__(self, config_file, module):
        self.config_file = config_file
        self.module = module
        self.klippy_apis = FakeKlippyApis(config_file, module)
        self.commands = []
        self.waits = []
        self.status = {
            "print_stats": {"state": "standby", "filename": ""},
            "extruder": {"target": 0},
            "heater_bed": {"target": 0},
            "gcode_macro KCTRL_STATE": {"ready": 1, "session_active": 0, "low_moves_armed": 0},
            "gcode_macro KCTRL_CAL_PATH_STATE": {"phase": "committed", "motion_armed": 0},
        }

    async def query_status(self):
        return self.status

    async def run_gcode(self, script, disconnect_ok=False):
        self.commands.append((script, disconnect_ok))
        if script == "RESTART":
            self.klippy_apis.loaded = self.module.ProbeCountFile(self.config_file).read()
        return "ok"

    async def update_mesh(self, matrix):
        return matrix

    async def wait_klippy_ready(self, timeout):
        self.waits.append(timeout)


class ProbeCountAdapterTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_component()

    @staticmethod
    def printer_config(count=(6, 6), algorithm="lagrange"):
        return (
            "[include helper.cfg]\n"
            "[bed_mesh]\n"
            "speed: 150\n"
            f"probe_count: {count[0]},{count[1]}\n"
            f"algorithm: {algorithm}\n"
            "fade_start: 5.0\n\n"
            "#*# [bed_mesh saved]\n"
            "#*# points = 0,0\n"
        ).encode("utf-8")

    def test_exact_rewrite_changes_only_count_and_compatible_algorithm(self):
        source = self.printer_config()
        rewritten, previous = self.module.ProbeCountFile._rewrite(
            source, ((9, 9), "bicubic")
        )
        self.assertEqual(previous, ((6, 6), "lagrange"))
        self.assertEqual(
            rewritten,
            source.replace(b"probe_count: 6,6", b"probe_count: 9,9").replace(
                b"algorithm: lagrange", b"algorithm: bicubic"
            ),
        )
        self.assertIn(b"#*# [bed_mesh saved]", rewritten)

    def test_even_spiral_matrix_and_ambiguous_config_fail_closed(self):
        with self.assertRaisesRegex(self.module.ProbeCountError, "compatible"):
            self.module.ProbeCountFile._rewrite(
                self.printer_config(), ((4, 4), "lagrange")
            )
        with self.assertRaisesRegex(self.module.ProbeCountError, "bicubic"):
            self.module.ProbeCountFile._rewrite(
                self.printer_config(), ((9, 9), "lagrange")
            )
        duplicated = (
            self.printer_config()
            + b"\n[bed_mesh]\nprobe_count: 6,6\nalgorithm: lagrange\n"
        )
        with self.assertRaisesRegex(self.module.ProbeCountError, "unique"):
            self.module.ProbeCountFile._rewrite(duplicated, ((9, 9), "bicubic"))

    async def test_backend_switches_before_clear_and_restores_after_heaters_off(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            printer = root / "printer.cfg"
            backup_root = root / "backups"
            campaign_id = "campaign-a"
            campaign_root = backup_root / campaign_id
            campaign_root.mkdir(parents=True)
            printer.write_bytes(self.printer_config())
            backup = campaign_root / "printer.cfg.before"
            backup.write_bytes(printer.read_bytes())
            evidence = {
                "root": str(campaign_root),
                "printer_cfg_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
            }
            backups = types.SimpleNamespace(printer_config=printer, backup_root=backup_root)
            orchestrator = types.SimpleNamespace(
                backups=backups,
                state={
                    "phase": "preparing",
                    "campaign_id": campaign_id,
                    "config": {"x_count": 9, "y_count": 9, "algorithm": "bicubic"},
                    "backup": evidence,
                },
            )
            backend = FakeBackend(printer, self.module)
            wrapped = self.module.ProbeCountAwareBackend(backend, orchestrator)
            await wrapped.run_gcode("BED_MESH_CLEAR")
            self.assertEqual(
                self.module.ProbeCountFile(printer).read(), ((9, 9), "bicubic")
            )
            self.assertEqual(backend.klippy_apis.loaded, ((9, 9), "bicubic"))
            self.assertEqual(backend.commands[:2], [("RESTART", True), ("BED_MESH_CLEAR", False)])
            self.assertTrue(wrapped.changed)

            orchestrator.state["phase"] = "mesh_ready"
            await wrapped.run_gcode("TURN_OFF_HEATERS")
            self.assertEqual(
                self.module.ProbeCountFile(printer).read(), ((6, 6), "lagrange")
            )
            self.assertEqual(backend.klippy_apis.loaded, ((6, 6), "lagrange"))
            self.assertEqual(backend.commands[-2:], [("TURN_OFF_HEATERS", False), ("RESTART", True)])
            self.assertFalse(wrapped.changed)

    def test_contract_declares_backup_restart_loaded_check_and_restore(self):
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(
            contract["contract_id"],
            "G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-MATRIX-V1",
        )
        runtime = contract["runtime"]
        self.assertTrue(runtime["backup_must_precede_change"])
        self.assertTrue(runtime["change_before_heat"])
        self.assertTrue(runtime["loaded_value_verified"])
        self.assertTrue(runtime["restore_after_heaters_off"])
        self.assertEqual(runtime["forbidden_probe_count"], [4, 4])
        self.assertEqual(
            runtime["changed_printer_cfg_fields"],
            ["bed_mesh.probe_count", "bed_mesh.algorithm"],
        )
        self.assertEqual(
            runtime["required_loaded_pairs"]["standard"],
            {"probe_count": [9, 9], "algorithm": "bicubic"},
        )

    def test_deployment_is_separate_and_has_no_physical_command(self):
        source = DEPLOYER.read_text(encoding="utf-8")
        self.assertIn("G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-MATRIX-V1", source)
        self.assertIn("S56k1_control_moonraker", source)
        for forbidden in (
            "KCTRL_MESH_CALIBRATE",
            "KCTRL_CALIBRATION_HOME",
            "M104",
            "M140",
            "G28",
        ):
            self.assertNotIn(forbidden, source)

    def test_manifest_pins_every_deployed_file(self):
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["contract_id"],
            "G4-K1-CONTROL-CALIBRATION-UI-PRTOUCH-MATRIX-V1",
        )
        self.assertEqual(
            hashlib.sha256(DEPLOYER.read_bytes()).hexdigest(),
            manifest["deployer"]["sha256"],
        )
        for item in manifest["files"]:
            self.assertEqual(
                hashlib.sha256((PACKAGE / item["source"]).read_bytes()).hexdigest(),
                item["sha256"],
            )


if __name__ == "__main__":
    unittest.main()
