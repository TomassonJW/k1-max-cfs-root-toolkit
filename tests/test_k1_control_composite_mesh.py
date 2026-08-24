import ast
import asyncio
import hashlib
import importlib.util
import json
import math
import shutil
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "packages" / "k1-control-v1" / "composite-mesh-v1" / "compose_mesh.py"
)
SPEC = importlib.util.spec_from_file_location("compose_mesh", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

PROFILE_MODULE_PATH = MODULE_PATH.with_name("render_profile.py")
PROFILE_SPEC = importlib.util.spec_from_file_location("render_profile", PROFILE_MODULE_PATH)
PROFILE_MODULE = importlib.util.module_from_spec(PROFILE_SPEC)
assert PROFILE_SPEC.loader is not None
PROFILE_SPEC.loader.exec_module(PROFILE_MODULE)

CORE_MODULE_PATH = MODULE_PATH.with_name("k1_control_composite_mesh_core.py")
CORE_SPEC = importlib.util.spec_from_file_location("composite_mesh_core", CORE_MODULE_PATH)
CORE_MODULE = importlib.util.module_from_spec(CORE_SPEC)
assert CORE_SPEC.loader is not None
CORE_SPEC.loader.exec_module(CORE_MODULE)

ARTIFACT_VALIDATOR_PATH = ROOT / "scripts" / "validate-k1-control-composite-mesh-artifacts.py"
ARTIFACT_SPEC = importlib.util.spec_from_file_location(
    "composite_mesh_artifact_validator", ARTIFACT_VALIDATOR_PATH
)
ARTIFACT_MODULE = importlib.util.module_from_spec(ARTIFACT_SPEC)
assert ARTIFACT_SPEC.loader is not None
ARTIFACT_SPEC.loader.exec_module(ARTIFACT_MODULE)

RECOVERY_VALIDATOR_PATH = ROOT / "scripts" / "validate-k1-control-composite-mesh-recovery.py"


def _context():
    return {
        "session_id": "synthetic-session",
        "plate_id": "PEI_TEXTURED_A",
        "bed_target_c": 55,
        "nozzle_target_c": 140,
        "homing_epoch": "home-1",
        "klipper_restart_count": 0,
    }


def _value(y, x):
    return round(0.003 * x * x - 0.002 * y + 0.0005 * x * y, 6)


def _document():
    return {
        "target": {
            "x_count": 11,
            "y_count": 11,
            "mesh_min": [5, 5],
            "mesh_max": [295, 295],
        },
        "passes": [
            {
                "name": layout["name"],
                "context": _context(),
                "x_indices": list(layout["x_indices"]),
                "y_indices": list(layout["y_indices"]),
                "mesh_min": list(layout["mesh_min"]),
                "mesh_max": list(layout["mesh_max"]),
                "probe_count": list(layout["probe_count"]),
                "algorithm": layout["algorithm"],
                "matrix": [
                    [_value(y, x) for x in layout["x_indices"]]
                    for y in layout["y_indices"]
                ],
            }
            for layout in MODULE.EXPECTED_11X11_LAYOUTS
        ],
    }


def _printer_config():
    return (
        b"[include helper.cfg]\n"
        b"[bed_mesh]\n"
        b"probe_count: 6,6\n\n"
        b"#*# <---------------------- SAVE_CONFIG ---------------------->\n"
        b"#*# DO NOT EDIT THIS BLOCK OR BELOW. The contents are auto-generated.\n"
        b"#*#\n"
        b"#*# [bed_mesh k1_p001_t055_r001_n06x06]\n"
        b"#*# version = 1\n"
        b"#*# points =\n"
        b"#*# \t0, 0, 0, 0, 0, 0\n"
        b"#*# \t0, 0, 0, 0, 0, 0\n"
        b"#*# \t0, 0, 0, 0, 0, 0\n"
        b"#*# \t0, 0, 0, 0, 0, 0\n"
        b"#*# \t0, 0, 0, 0, 0, 0\n"
        b"#*# \t0, 0, 0, 0, 0, 0\n"
    )


def _runtime_status():
    return {
        "print_stats": {"state": "standby", "filename": ""},
        "extruder": {"target": 0.0, "temperature": 25.0},
        "heater_bed": {"target": 0.0, "temperature": 25.0},
        "toolhead": {"homed_axes": ""},
        "gcode_macro KCTRL_STATE": {
            "ready": 1,
            "accepted_z_valid": 1,
            "session_active": 0,
            "low_moves_armed": 0,
            "expected_nozzle_c": 0,
            "temperature_owner": "none",
        },
        "gcode_macro KCTRL_CAL_PATH_STATE": {
            "phase": "committed",
            "motion_armed": 0,
            "commit_ready": 0,
        },
        "bed_mesh": {
            "profile_name": CORE_MODULE.ROBUST_PROFILE,
            "probed_matrix": [[0.0] * 6 for _ in range(6)],
            "profiles": {
                CORE_MODULE.ROBUST_PROFILE: {"points": [[0.0] * 6 for _ in range(6)]}
            },
        },
        "box": {"T1": {"state": "connect"}, "T2": {"state": "connect"}},
    }


class _Store:
    def __init__(self):
        self.value = CORE_MODULE.default_state()

    def load(self):
        return json.loads(json.dumps(self.value))

    def save(self, value):
        self.value = json.loads(json.dumps(value))


class _Clock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    async def sleep(self, seconds):
        self.value += seconds
        await asyncio.sleep(0)


class _Backups:
    def __init__(self, root):
        self.root = Path(root)
        self.printer_config = self.root / "printer.cfg"
        self.z_state = self.root / "k1-control-z-state.json"
        self.printer_config.write_bytes(_printer_config())
        self.z_state.write_text('{"integrity":"ok"}\n', encoding="utf-8")
        self.created = []
        self.restored = []

    @staticmethod
    def _hash(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def create(self, campaign_id):
        backup = self.root / "backups" / campaign_id
        backup.mkdir(parents=True)
        config_copy = backup / "printer.cfg.before"
        z_copy = backup / "k1-control-z-state.json.before"
        shutil.copy2(self.printer_config, config_copy)
        shutil.copy2(self.z_state, z_copy)
        evidence = {
            "root": str(backup),
            "printer_cfg_sha256": self._hash(config_copy),
            "z_state_present": True,
            "z_state_sha256": self._hash(z_copy),
        }
        self.created.append(campaign_id)
        return evidence

    def restore(self, campaign_id, evidence):
        backup = Path(evidence["root"])
        shutil.copy2(backup / "printer.cfg.before", self.printer_config)
        shutil.copy2(backup / "k1-control-z-state.json.before", self.z_state)
        self.restored.append(campaign_id)
        return evidence


class _Backend:
    def __init__(self, printer_config, lose_homing_after=None, fail_target_load=False):
        self.printer_config = Path(printer_config)
        self.status = _runtime_status()
        self.commands = []
        self.waits = []
        self.captured = []
        self.lose_homing_after = lose_homing_after
        self.fail_target_load = fail_target_load
        self.restart_count = 0

    async def query_status(self):
        return self.status

    async def wait_klippy_ready(self, timeout):
        self.waits.append(timeout)

    def _capture(self, layout):
        matrix = [
            [_value(y, x) for x in layout["x_indices"]]
            for y in layout["y_indices"]
        ]
        item = {
            "name": layout["name"],
            "context": _context(),
            "x_indices": list(layout["x_indices"]),
            "y_indices": list(layout["y_indices"]),
            "mesh_min": list(layout["mesh_min"]),
            "mesh_max": list(layout["mesh_max"]),
            "probe_count": list(layout["probe_count"]),
            "algorithm": "lagrange",
            "matrix": matrix,
        }
        self.captured.append(item)
        self.status["bed_mesh"]["profile_name"] = layout["profile"]
        self.status["bed_mesh"]["probed_matrix"] = matrix
        self.status["bed_mesh"]["profiles"][layout["profile"]] = {"points": matrix}
        if self.lose_homing_after == len(self.captured):
            self.status["toolhead"]["homed_axes"] = ""

    async def run_gcode(self, command, disconnect_ok=False):
        self.commands.append((command, disconnect_ok))
        if command == "M140 S55":
            self.status["heater_bed"].update(target=55.0, temperature=55.0)
        elif command == "M104 S140":
            self.status["extruder"].update(target=140.0, temperature=140.0)
        elif command == "KCTRL_CALIBRATION_HOME":
            self.status["toolhead"]["homed_axes"] = "xyz"
        elif command.startswith("BED_MESH_CALIBRATE PROFILE="):
            for layout in CORE_MODULE.PASS_LAYOUTS:
                if "PROFILE=%s " % layout["profile"] in command:
                    self._capture(layout)
                    break
            else:
                raise RuntimeError("unknown composite pass")
        elif command == "TURN_OFF_HEATERS":
            self.status["heater_bed"]["target"] = 0.0
            self.status["extruder"]["target"] = 0.0
        elif command == "RESTART":
            self.restart_count += 1
            self.status["toolhead"]["homed_axes"] = ""
            self.status["bed_mesh"]["profiles"] = {
                CORE_MODULE.ROBUST_PROFILE: {"points": [[0.0] * 6 for _ in range(6)]}
            }
            self.status["bed_mesh"]["profile_name"] = CORE_MODULE.ROBUST_PROFILE
            self.status["bed_mesh"]["probed_matrix"] = [[0.0] * 6 for _ in range(6)]
            target_header = (
                "#*# [bed_mesh %s]" % CORE_MODULE.TARGET_PROFILE
            ).encode("ascii")
            if target_header in self.printer_config.read_bytes() and len(self.captured) == 4:
                target = MODULE.compose_11x11({
                    "target": {
                        "x_count": 11,
                        "y_count": 11,
                        "mesh_min": [5, 5],
                        "mesh_max": [295, 295],
                    },
                    "passes": self.captured,
                })["candidate_matrix"]
                self.status["bed_mesh"]["profiles"][CORE_MODULE.TARGET_PROFILE] = {
                    "points": target
                }
        elif command == "BED_MESH_PROFILE LOAD=%s" % CORE_MODULE.TARGET_PROFILE:
            if self.fail_target_load:
                raise RuntimeError("synthetic target load failure")
            target = self.status["bed_mesh"]["profiles"].get(CORE_MODULE.TARGET_PROFILE)
            if not target:
                raise RuntimeError("target profile absent")
            self.status["bed_mesh"]["profile_name"] = CORE_MODULE.TARGET_PROFILE
            self.status["bed_mesh"]["probed_matrix"] = target["points"]
        elif command == "BED_MESH_PROFILE LOAD=%s" % CORE_MODULE.ROBUST_PROFILE:
            self.status["bed_mesh"]["profile_name"] = CORE_MODULE.ROBUST_PROFILE
            self.status["bed_mesh"]["probed_matrix"] = [[0.0] * 6 for _ in range(6)]
        elif "VARIABLE=expected_nozzle_c VALUE=" in command:
            self.status["gcode_macro KCTRL_STATE"]["expected_nozzle_c"] = int(
                command.rsplit("=", 1)[1]
            )
        elif "VARIABLE=temperature_owner VALUE=" in command:
            self.status["gcode_macro KCTRL_STATE"]["temperature_owner"] = (
                "calibration" if "calibration" in command else "none"
            )
        return "ok"


class CompositeMeshTests(unittest.TestCase):
    def test_sources_parse_with_python_38_grammar(self):
        for path in (
            MODULE_PATH,
            PROFILE_MODULE_PATH,
            CORE_MODULE_PATH,
            MODULE_PATH.with_name("k1_control_composite_mesh.py"),
            ARTIFACT_VALIDATOR_PATH,
            RECOVERY_VALIDATOR_PATH,
        ):
            ast.parse(
                path.read_text(encoding="utf-8"),
                filename=path.name,
                feature_version=(3, 8),
            )

    def test_contract_keeps_the_composite_path_offline_and_bounded(self):
        contract_path = MODULE_PATH.with_name("composite-mesh-contract.json")
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertEqual(contract["status"], "deployment_candidate")
        self.assertTrue(contract["printer_mutation_authorized"])
        self.assertEqual(contract["target"]["physical_points"], 121)
        self.assertEqual(contract["target"]["physical_contacts"], 144)
        self.assertEqual(
            max(item["physical_points"] for item in contract["bounded_passes"]),
            36,
        )
        self.assertTrue(
            all(item["shape"] == "6x6" for item in contract["bounded_passes"])
        )
        self.assertFalse(contract["hard_guards"]["prtouch_version_change"])
        self.assertFalse(contract["hard_guards"]["remove_factory_hold_tables"])
        self.assertTrue(contract["hard_guards"]["atomic_profile_persistence"])
        self.assertTrue(
            contract["hard_guards"]["single_klipper_restart_after_four_passes"]
        )

    def test_deployment_manifest_pins_candidate_and_exact_machine_parser(self):
        manifest = json.loads(
            MODULE_PATH.with_name("deployment-manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["contract_id"], CORE_MODULE.GATE_ID)
        self.assertEqual(manifest["status"], "deployment_candidate")
        for key in ("deployer", "runner", "artifact_validator"):
            path = ROOT / manifest[key]["path"]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(), manifest[key]["sha256"]
            )
        contract = MODULE_PATH.with_name(manifest["contract"]["path"])
        self.assertEqual(
            hashlib.sha256(contract.read_bytes()).hexdigest(),
            manifest["contract"]["sha256"],
        )
        for item in manifest["files"]:
            source = MODULE_PATH.parent / item["source"]
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), item["sha256"])
        self.assertEqual(
            manifest["baseline"]["printer_cfg_sha256"],
            "e1f6cd6dc92c9eea1e105f8c669f6d246753243535f09c7f9d92e2dfafebac14",
        )
        parser = next(
            item
            for item in manifest["firmware_dependencies"]
            if item["path"] == "/usr/share/klipper/klippy/configfile.py"
        )
        self.assertEqual(
            parser["sha256"],
            "230f37d5c3d4ccb28daf4d698ac05fd2002d667de46a49daa21ff17dea3084af",
        )

    def test_recovery_manifest_pins_retained_capture_and_upgrade_delta(self):
        manifest = json.loads(
            MODULE_PATH.with_name("recovery-deployment-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            manifest["contract_id"], CORE_MODULE.RECOVERY_GATE_ID
        )
        self.assertEqual(manifest["baseline"]["physical_contacts"], 144)
        self.assertEqual(manifest["baseline"]["unique_physical_points"], 121)
        self.assertLessEqual(manifest["baseline"]["aligned_maximum_spread_mm"], 0.05)
        for key in ("deployer", "runner", "validator"):
            path = ROOT / manifest[key]["path"]
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(), manifest[key]["sha256"]
            )
        contract = MODULE_PATH.with_name(manifest["contract"]["path"])
        self.assertEqual(
            hashlib.sha256(contract.read_bytes()).hexdigest(),
            manifest["contract"]["sha256"],
        )
        for item in manifest["files"]:
            source = MODULE_PATH.parent / item["source"]
            self.assertEqual(
                hashlib.sha256(source.read_bytes()).hexdigest(), item["sha256"]
            )

    def test_remote_parser_program_separates_preamble_from_embedded_sources(self):
        deployer = (ROOT / "scripts" / "deploy-k1-control-composite-mesh-v1.ps1").read_text(
            encoding="utf-8-sig"
        )
        preamble_end = deployer.index('    $program += "`n"')
        source_loop = deployer.index("    foreach ($name in $sources.Keys)")
        self.assertLess(preamble_end, source_loop)

    def test_four_bounded_passes_rebuild_exact_11_by_11_surface(self):
        result = MODULE.compose_11x11(_document())
        self.assertTrue(result["accepted"])
        self.assertEqual(result["pass_count"], 4)
        self.assertEqual(result["physical_points"], 121)
        self.assertEqual(result["physical_contacts"], 144)
        self.assertEqual(result["unique_physical_points"], 121)
        self.assertEqual(result["duplicate_contacts"], 23)
        self.assertEqual(result["overlap_positions"], 21)
        self.assertEqual(result["overlap_mm"]["maximum_spread"], 0.0)
        self.assertEqual(result["maximum_contacts_per_pass"], 36)
        self.assertEqual(result["mesh_params"]["algo"], "bicubic")
        expected = [[_value(y, x) for x in range(11)] for y in range(11)]
        self.assertEqual(result["candidate_matrix"], expected)

    def test_rejects_more_than_36_contacts_in_one_pass(self):
        document = _document()
        document["passes"][0]["x_indices"] = list(range(7))
        document["passes"][0]["matrix"] = [
            [_value(y, x) for x in range(7)]
            for y in document["passes"][0]["y_indices"]
        ]
        with self.assertRaisesRegex(ValueError, "dépassent la limite de 36"):
            MODULE.compose(document)

    def test_rejects_different_physical_session(self):
        document = _document()
        document["passes"][2]["context"]["homing_epoch"] = "home-2"
        with self.assertRaisesRegex(ValueError, "même session physique"):
            MODULE.compose(document)

    def test_rejects_klipper_restart_between_subgrids(self):
        document = _document()
        document["passes"][1]["context"]["klipper_restart_count"] = 1
        with self.assertRaisesRegex(ValueError, "aucun redémarrage Klipper"):
            MODULE.compose(document)

    def test_rejects_incomplete_coverage(self):
        document = _document()
        document["passes"].pop()
        with self.assertRaisesRegex(ValueError, "couverture incomplète"):
            MODULE.compose(document)

    def test_overlaps_are_averaged_and_bounded(self):
        document = _document()
        document["passes"][1]["matrix"][0][0] += 0.02
        result = MODULE.compose_11x11(document)
        self.assertAlmostEqual(result["raw_overlap_mm"]["maximum_spread"], 0.02, places=9)
        self.assertLess(result["overlap_mm"]["maximum_spread"], 0.02)
        self.assertAlmostEqual(sum(result["pass_offsets_mm"].values()), 0.0, places=12)

        document["passes"][1]["matrix"][0][0] += 0.20
        with self.assertRaisesRegex(ValueError, "dépasse 0,05 mm"):
            MODULE.compose_11x11(document)

    def test_constant_pass_biases_are_stitched_without_changing_global_mean(self):
        document = _document()
        biases = {
            "north_west": 0.04,
            "north_east": 0.04,
            "south_west": 0.14,
            "south_east": 0.14,
        }
        for item in document["passes"]:
            bias = biases[item["name"]]
            for row in item["matrix"]:
                for index in range(len(row)):
                    row[index] += bias
        result = MODULE.compose_11x11(document)
        self.assertAlmostEqual(result["raw_overlap_mm"]["maximum_spread"], 0.10, places=9)
        self.assertAlmostEqual(result["overlap_mm"]["maximum_spread"], 0.0, places=9)
        self.assertAlmostEqual(
            sum(result["pass_offsets_mm"].values()), 0.0, places=12
        )

    def test_rejects_non_finite_measurement(self):
        document = _document()
        document["passes"][3]["matrix"][0][0] = math.nan
        with self.assertRaisesRegex(ValueError, "valeur finie"):
            MODULE.compose(document)

    def test_strict_recipe_rejects_reordered_or_shifted_partition(self):
        reordered = _document()
        reordered["passes"][0], reordered["passes"][1] = (
            reordered["passes"][1], reordered["passes"][0]
        )
        with self.assertRaisesRegex(ValueError, "recette physique north_west"):
            MODULE.compose_11x11(reordered)

        shifted = _document()
        shifted["passes"][3]["mesh_min"] = [151, 150]
        with self.assertRaisesRegex(ValueError, "recette physique south_east"):
            MODULE.compose_11x11(shifted)

    def test_profile_renderer_appends_exact_11x11_block_without_touching_robust(self):
        matrix = MODULE.compose_11x11(_document())["candidate_matrix"]
        source = _printer_config()
        rendered = PROFILE_MODULE.append_profile(source, matrix)
        self.assertTrue(rendered.startswith(source))
        self.assertEqual(
            rendered.count(b"#*# [bed_mesh k1_p001_t055_r001_n06x06]"), 1
        )
        self.assertEqual(
            rendered.count(b"#*# [bed_mesh k1_p001_t055_r001_n11x11]"), 1
        )
        self.assertIn(b"#*# x_count = 11\n#*# y_count = 11", rendered)
        self.assertIn(b"#*# algo = bicubic", rendered)
        block = rendered.split(b"#*# [bed_mesh k1_p001_t055_r001_n11x11]", 1)[1]
        point_rows = [line for line in block.splitlines() if line.startswith(b"#*# \t")]
        self.assertEqual(len(point_rows), 11)
        self.assertTrue(all(len(row.split(b",")) == 11 for row in point_rows))

    def test_profile_renderer_refuses_missing_baseline_existing_target_and_nonfinite(self):
        matrix = MODULE.compose_11x11(_document())["candidate_matrix"]
        with self.assertRaisesRegex(ValueError, "SAVE_CONFIG exact doit être unique"):
            PROFILE_MODULE.append_profile(b"[bed_mesh]\n", matrix)
        existing = PROFILE_MODULE.append_profile(_printer_config(), matrix)
        with self.assertRaisesRegex(ValueError, "existe déjà"):
            PROFILE_MODULE.append_profile(existing, matrix)
        matrix[0][0] = math.inf
        with self.assertRaisesRegex(ValueError, "valeur non finie"):
            PROFILE_MODULE.append_profile(_printer_config(), matrix)

    def test_artifact_validator_requires_exact_rendered_candidate(self):
        result = MODULE.compose_11x11(_document())
        state = {
            "phase": "qualified",
            "candidate_matrix": result["candidate_matrix"],
            "physical_contacts": 144,
            "completed_passes": 4,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backup = root / "before.cfg"
            current = root / "current.cfg"
            state_path = root / "state.json"
            backup.write_bytes(_printer_config())
            rendered = PROFILE_MODULE.append_profile(
                backup.read_bytes(), result["candidate_matrix"]
            )
            current.write_bytes(rendered)
            state["candidate_printer_cfg_sha256"] = hashlib.sha256(rendered).hexdigest()
            state_path.write_text(json.dumps(state), encoding="utf-8")
            validated = ARTIFACT_MODULE.validate(backup, current, state_path)
            current.write_bytes(rendered + b"# drift\n")
            with self.assertRaisesRegex(ValueError, "exact rendered candidate"):
                ARTIFACT_MODULE.validate(backup, current, state_path)
        self.assertEqual(validated["result"], "VALIDATE_COMPOSITE_MESH_ARTIFACTS_OK")


class CompositeMeshOrchestratorTests(unittest.IsolatedAsyncioTestCase):
    def build(self, directory, lose_homing_after=None, fail_target_load=False):
        backups = _Backups(directory)
        backend = _Backend(
            backups.printer_config,
            lose_homing_after=lose_homing_after,
            fail_target_load=fail_target_load,
        )
        store = _Store()
        clock = _Clock()
        orchestrator = CORE_MODULE.CompositeMeshOrchestrator(
            backend,
            store,
            backups,
            MODULE.compose_11x11,
            PROFILE_MODULE.append_profile,
            clock=clock,
            sleep=clock.sleep,
        )
        return orchestrator, backend, store, backups

    async def test_four_pass_campaign_persists_then_returns_to_robust_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator, backend, store, backups = self.build(directory)
            result = await orchestrator.run(CORE_MODULE.GATE_ID, True)
            persisted = backups.printer_config.read_bytes()
        self.assertEqual(result["phase"], "qualified")
        self.assertEqual(result["completed_passes"], 4)
        self.assertEqual(result["physical_contacts"], 144)
        self.assertEqual(result["qualification"]["physical_points"], 121)
        self.assertEqual(result["qualification"]["physical_contacts"], 144)
        self.assertEqual(len(backups.created), 1)
        self.assertEqual(backups.restored, [])
        self.assertEqual(backend.restart_count, 1)
        mesh_commands = [
            command
            for command, _ in backend.commands
            if command.startswith("BED_MESH_CALIBRATE PROFILE=")
        ]
        self.assertEqual(len(mesh_commands), 4)
        self.assertEqual(
            backend.status["bed_mesh"]["profile_name"], CORE_MODULE.ROBUST_PROFILE
        )
        self.assertIn(CORE_MODULE.TARGET_PROFILE, backend.status["bed_mesh"]["profiles"])
        self.assertEqual(backend.status["extruder"]["target"], 0.0)
        self.assertEqual(backend.status["heater_bed"]["target"], 0.0)
        self.assertEqual(backend.status["toolhead"]["homed_axes"], "")
        self.assertIn(
            ("#*# [bed_mesh %s]" % CORE_MODULE.TARGET_PROFILE).encode("ascii"),
            persisted,
        )
        self.assertEqual(store.value["phase"], "qualified")

    async def test_complete_failed_capture_is_recovered_without_new_physical_command(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator, backend, store, backups = self.build(directory)
            document = _document()
            campaign_id = "retained-four-pass-capture"
            backup = backups.create(campaign_id)
            retained = CORE_MODULE.default_state()
            retained.update({
                "phase": "failed",
                "busy": False,
                "campaign_id": campaign_id,
                "last_error": "synthetic overlap rejection",
                "passes": document["passes"],
                "backup": backup,
                "config_written": False,
            })
            store.value = json.loads(json.dumps(retained))
            orchestrator.state = store.load()
            backend.captured = document["passes"]
            result = await orchestrator.recover_complete_capture(
                CORE_MODULE.RECOVERY_GATE_ID
            )
        self.assertEqual(result["phase"], "qualified")
        self.assertEqual(result["physical_contacts"], 144)
        self.assertEqual(result["qualification"]["unique_physical_points"], 121)
        self.assertEqual(backend.restart_count, 1)
        forbidden = (
            "M140 ",
            "M104 ",
            "NOZZLE_CLEAR",
            "KCTRL_CALIBRATION_HOME",
            "BED_MESH_CALIBRATE",
        )
        self.assertFalse(
            any(command.startswith(forbidden) for command, _ in backend.commands)
        )

    async def test_recovery_requires_exact_gate_and_complete_failed_state(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator, _, _, _ = self.build(directory)
            with self.assertRaisesRegex(CORE_MODULE.CompositeMeshError, "gate de reprise"):
                await orchestrator.recover_complete_capture("GO")
            with self.assertRaisesRegex(CORE_MODULE.CompositeMeshError, "capture complète"):
                await orchestrator.recover_complete_capture(CORE_MODULE.RECOVERY_GATE_ID)

    async def test_lost_single_homing_aborts_and_restores_exact_baseline(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator, backend, store, backups = self.build(
                directory, lose_homing_after=2
            )
            baseline = backups.printer_config.read_bytes()
            with self.assertRaisesRegex(CORE_MODULE.CompositeMeshError, "référence XYZ"):
                await orchestrator.run(CORE_MODULE.GATE_ID, True)
            final_config = backups.printer_config.read_bytes()
        self.assertEqual(store.value["phase"], "failed")
        self.assertEqual(final_config, baseline)
        self.assertEqual(backend.status["extruder"]["target"], 0.0)
        self.assertEqual(backend.status["heater_bed"]["target"], 0.0)
        self.assertEqual(backend.status["toolhead"]["homed_axes"], "")
        self.assertEqual(
            backend.status["bed_mesh"]["profile_name"], CORE_MODULE.ROBUST_PROFILE
        )
        self.assertNotIn(CORE_MODULE.TARGET_PROFILE, backend.status["bed_mesh"]["profiles"])

    async def test_failure_after_persistence_restores_backup_and_removes_target(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator, backend, store, backups = self.build(
                directory, fail_target_load=True
            )
            baseline = backups.printer_config.read_bytes()
            with self.assertRaisesRegex(CORE_MODULE.CompositeMeshError, "target load failure"):
                await orchestrator.run(CORE_MODULE.GATE_ID, True)
            final_config = backups.printer_config.read_bytes()
        self.assertEqual(store.value["phase"], "failed")
        self.assertEqual(final_config, baseline)
        self.assertEqual(len(backups.restored), 1)
        self.assertGreaterEqual(backend.restart_count, 2)
        self.assertNotIn(CORE_MODULE.TARGET_PROFILE, backend.status["bed_mesh"]["profiles"])
        self.assertEqual(
            backend.status["bed_mesh"]["profile_name"], CORE_MODULE.ROBUST_PROFILE
        )

    async def test_gate_and_fresh_plate_are_required_before_any_command(self):
        with tempfile.TemporaryDirectory() as directory:
            orchestrator, backend, _, _ = self.build(directory)
            with self.assertRaisesRegex(CORE_MODULE.CompositeMeshError, "gate composite"):
                await orchestrator.run("GO", True)
            with self.assertRaisesRegex(CORE_MODULE.CompositeMeshError, "plateau libre"):
                await orchestrator.run(CORE_MODULE.GATE_ID, False)
        self.assertEqual(backend.commands, [])

    def test_campaign_state_uses_shared_version_marker(self):
        state = CORE_MODULE.default_state()
        self.assertEqual(state["version"], 1)
        self.assertNotIn("schema", state)


if __name__ == "__main__":
    unittest.main()
