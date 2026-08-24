import copy
import ast
import importlib
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "k1-control-v1" / "mesh-editor-offline-v1"
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

core = importlib.import_module("mesh_editor_core")
klipper = importlib.import_module("klipper_profile")
fake_api = importlib.import_module("fake_api")
server_module = importlib.import_module("server")


class SourceAndInterpolationTests(unittest.TestCase):
    def test_sanitized_source_is_exact_and_immutable(self):
        source = core.load_source_document()
        matrix = core.load_source_matrix()
        self.assertTrue(source["immutable"])
        self.assertEqual(source["source_id"], core.SOURCE_ID)
        self.assertEqual(matrix[0][0], Decimal("0.180747"))
        self.assertEqual(matrix[10][10], Decimal("0.008730"))
        self.assertEqual(
            source["matrix_sha256"],
            "bee530fb9738773d1f2ccb63d47743e15776690f1bcdf92a3daac7661f0f50bf",
        )
        self.assertEqual(
            core.source_matrix_sha256(matrix),
            source["matrix_sha256"],
        )
        self.assertEqual(source["geometry"]["row_order"], "min_y_to_max_y")
        serialized = json.dumps(source, sort_keys=True)
        self.assertNotIn("inventory/raw", serialized)
        self.assertNotIn("192.168.", serialized)
        self.assertNotIn("10.0.", serialized)

    def test_bicubic_surface_contains_all_physical_points(self):
        source = core.load_source_matrix()
        surface = core.bicubic_surface(source)
        self.assertEqual(len(surface), 31)
        self.assertTrue(all(len(row) == 31 for row in surface))
        for row in range(11):
            for column in range(11):
                self.assertEqual(surface[row * 3][column * 3], source[row][column])

    def test_constant_surface_mean_is_constant(self):
        constant = tuple(
            tuple(Decimal("0.017") for _column in range(11))
            for _row in range(11)
        )
        self.assertEqual(core.weighted_surface_mean(constant), Decimal("0.017"))

    def test_normalization_is_zero_on_interpolated_surface(self):
        requested = [list(row) for row in core.zero_matrix()]
        requested[5][5] = Decimal("-0.010")
        normalized = core.normalize_requested_delta(requested)
        self.assertLessEqual(
            abs(core.weighted_surface_mean(normalized)),
            core.ZERO_MEAN_TOLERANCE,
        )
        self.assertLess(normalized[5][5], 0)
        self.assertGreater(normalized[0][0], 0)

    def test_substituted_source_document_is_refused(self):
        source = core.load_source_document()
        substituted = copy.deepcopy(source)
        substituted["points_mm"][0][1] = "9.000000"
        with self.assertRaisesRegex(core.MeshEditorError, "fixture figée"):
            core.MeshEditor(substituted)


class SelectionAndGuardTests(unittest.TestCase):
    def test_all_selection_modes_are_bounded(self):
        self.assertEqual(
            core.selected_cells({"mode": "point", "row": 2, "column": 3}),
            ((2, 3),),
        )
        self.assertEqual(
            len(core.selected_cells({"mode": "row", "row": 4})),
            11,
        )
        self.assertEqual(
            len(core.selected_cells({"mode": "column", "column": 7})),
            11,
        )
        region = core.selected_cells(
            {
                "mode": "region",
                "row_start": 5,
                "row_end": 3,
                "column_start": 7,
                "column_end": 5,
            }
        )
        self.assertEqual(len(region), 9)
        self.assertEqual(region[0], (3, 5))
        self.assertEqual(region[-1], (5, 7))

    def test_large_region_is_refused(self):
        with self.assertRaisesRegex(core.MeshEditorError, "3 x 3"):
            core.selected_cells(
                {
                    "mode": "region",
                    "row_start": 0,
                    "row_end": 3,
                    "column_start": 0,
                    "column_end": 2,
                }
            )

    def test_direction_semantics_and_allowed_steps(self):
        editor = core.MeshEditor()
        selection = {"mode": "point", "row": 5, "column": 5}
        editor.apply_correction(selection, "closer", "0.005")
        self.assertEqual(editor.requested_delta[5][5], Decimal("-0.005"))
        editor.apply_correction(selection, "farther", "0.010")
        self.assertEqual(editor.requested_delta[5][5], Decimal("0.005"))
        with self.assertRaisesRegex(core.MeshEditorError, "0,005"):
            editor.apply_correction(selection, "farther", "0.020")

    def test_warning_then_neighbor_refusal_preserves_state(self):
        editor = core.MeshEditor()
        selection = {"mode": "point", "row": 5, "column": 5}
        result = None
        for _attempt in range(6):
            result = editor.apply_correction(selection, "farther", "0.010")
        self.assertTrue(result["warnings"])
        for _attempt in range(2):
            editor.apply_correction(selection, "farther", "0.010")
        before = editor.state()
        with self.assertRaisesRegex(core.MeshEditorError, "voisin"):
            editor.apply_correction(selection, "farther", "0.010")
        self.assertEqual(editor.state(), before)


class HistoryAndExportTests(unittest.TestCase):
    def setUp(self):
        self.editor = core.MeshEditor()
        self.point = {"mode": "point", "row": 4, "column": 6}

    def test_undo_redo_branch_and_restore_are_explicit(self):
        source = self.editor.state()["final_matrix"]
        self.editor.apply_correction(self.point, "closer", "0.005")
        changed = self.editor.state()["final_matrix"]
        self.assertNotEqual(changed, source)
        self.editor.undo()
        self.assertEqual(self.editor.state()["final_matrix"], source)
        self.editor.redo()
        self.assertEqual(self.editor.state()["final_matrix"], changed)
        self.editor.restore_source()
        restored = self.editor.state()
        self.assertEqual(restored["final_matrix"], source)
        self.assertEqual(restored["history"][-1]["kind"], "restore_source")

    def test_new_edit_after_undo_discards_redo_branch(self):
        self.editor.apply_correction(self.point, "closer", "0.005")
        self.editor.apply_correction(self.point, "closer", "0.005")
        self.editor.undo()
        self.editor.apply_correction(self.point, "farther", "0.005")
        state = self.editor.state()
        self.assertFalse(state["can_redo"])
        self.assertEqual(len(state["history"]), 2)

    def test_canonical_export_is_deterministic_and_valid(self):
        self.editor.apply_correction(self.point, "closer", "0.010")
        first = self.editor.export_document()
        second = self.editor.export_document()
        self.assertEqual(first, second)
        core.validate_derived_document(first)
        self.assertFalse(first["global_z"]["included"])
        self.assertEqual(len(first["matrices_mm"]["final"]), 11)
        self.assertTrue(all(len(row) == 11 for row in first["matrices_mm"]["final"]))

    def test_tampered_export_is_refused(self):
        document = self.editor.export_document()
        tampered = copy.deepcopy(document)
        tampered["matrices_mm"]["source"][0][0] = "99.000000"
        with self.assertRaises(core.MeshEditorError):
            core.validate_derived_document(tampered)

    def test_klipper_export_has_121_values_and_rounds_safely(self):
        self.editor.apply_correction(self.point, "closer", "0.010")
        document = self.editor.export_document()
        first = klipper.render_klipper_profile(document)
        second = klipper.render_klipper_profile(document)
        self.assertEqual(first, second)
        self.assertEqual(klipper.canonical_round_trip(first), first)
        parsed = klipper.parse_klipper_profile(first)
        self.assertEqual(len(parsed["matrix"]), 11)
        self.assertTrue(all(len(row) == 11 for row in parsed["matrix"]))
        source = core.load_source_matrix()
        delta = tuple(
            tuple(
                parsed["matrix"][row][column] - source[row][column]
                for column in range(11)
            )
            for row in range(11)
        )
        self.assertLessEqual(
            abs(core.weighted_surface_mean(delta)),
            klipper.EXPORTED_MEAN_TOLERANCE,
        )
        self.assertIn("# global_z_included = false", first)
        self.assertNotIn("SAVE_CONFIG", first)

    def test_klipper_parser_refuses_tampered_metadata(self):
        block = klipper.render_klipper_profile(self.editor.export_document())
        tampered = block.replace(
            "# global_z_included = false",
            "# global_z_included = true",
        )
        with self.assertRaisesRegex(core.MeshEditorError, "Z global"):
            klipper.parse_klipper_profile(tampered)
        tampered_source = block.replace(
            core.PINNED_SOURCE_MATRIX_SHA256,
            "0" * 64,
        )
        with self.assertRaisesRegex(core.MeshEditorError, "empreinte source"):
            klipper.parse_klipper_profile(tampered_source)


class FakeApiAndIsolationTests(unittest.TestCase):
    def test_full_create_correct_undo_redo_export_flow(self):
        api = fake_api.FakeMeshEditorApi()
        status, body, _content_type = api.handle(
            "POST",
            "/api/mesh-editor/v1/profiles",
            {"source_id": core.SOURCE_ID, "version": 1},
        )
        self.assertEqual(status, 201)
        profile_id = body["profile"]["profile_id"]
        correction_path = (
            "/api/mesh-editor/v1/profiles/" + profile_id + "/corrections"
        )
        status, body, _content_type = api.handle(
            "POST",
            correction_path,
            {
                "selection": {"mode": "row", "row": 3},
                "direction": "closer",
                "step_mm": "0.005",
            },
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["state"]["can_undo"])
        actions_path = "/api/mesh-editor/v1/profiles/" + profile_id + "/actions"
        self.assertEqual(
            api.handle("POST", actions_path, {"action": "undo"})[0],
            200,
        )
        self.assertEqual(
            api.handle("POST", actions_path, {"action": "redo"})[0],
            200,
        )
        export_path = "/api/mesh-editor/v1/profiles/" + profile_id + "/export/"
        json_export = api.handle("GET", export_path + "json")[1]
        klipper_export = api.handle("GET", export_path + "klipper")[1]
        self.assertEqual(json.loads(json_export)["profile_id"], profile_id)
        self.assertIn("#*# [bed_mesh " + profile_id + "]", klipper_export)

    def test_simulated_validation_error_never_mutates(self):
        api = fake_api.FakeMeshEditorApi()
        api.handle(
            "POST",
            "/api/mesh-editor/v1/profiles",
            {"source_id": core.SOURCE_ID, "version": 1},
        )
        before = api.editor.state()
        api.handle(
            "POST",
            "/api/mesh-editor/v1/simulation",
            {"scenario": "validation_error"},
        )
        path = (
            "/api/mesh-editor/v1/profiles/"
            + core.DERIVED_PROFILE_ID
            + "/corrections"
        )
        status, _body, _content_type = api.handle(
            "POST",
            path,
            {
                "selection": {"mode": "point", "row": 0, "column": 0},
                "direction": "closer",
                "step_mm": "0.005",
            },
        )
        self.assertEqual(status, 422)
        self.assertEqual(api.editor.state(), before)

    def test_server_is_bound_only_to_loopback(self):
        local_server = server_module.create_server(0)
        second_server = server_module.create_server(0)
        try:
            self.assertEqual(local_server.server_address[0], "127.0.0.1")
            local_server.mesh_editor_api.handle(
                "POST",
                "/api/mesh-editor/v1/profiles",
                {"source_id": core.SOURCE_ID, "version": 1},
            )
            self.assertIsNotNone(local_server.mesh_editor_api.editor)
            self.assertIsNone(second_server.mesh_editor_api.editor)
        finally:
            local_server.server_close()
            second_server.server_close()

    def test_runtime_sources_contain_no_printer_transport(self):
        runtime_files = [
            PACKAGE / "fake_api.py",
            PACKAGE / "server.py",
            PACKAGE / "www" / "app.mjs",
        ]
        joined = "\n".join(path.read_text(encoding="utf-8") for path in runtime_files)
        forbidden = [
            "paramiko",
            "subprocess",
            "/printer/",
            "/machine/",
            "websocket",
            "requests.",
            "http://192.",
            "https://192.",
        ]
        for marker in forbidden:
            self.assertNotIn(marker, joined.lower())

    def test_python_sources_parse_with_the_moonraker_python_grammar(self):
        for path in PACKAGE.glob("*.py"):
            ast.parse(
                path.read_text(encoding="utf-8"),
                filename=str(path),
                feature_version=(3, 8),
            )

    def test_ui_contract_exposes_all_required_actions(self):
        html = (PACKAGE / "www" / "index.html").read_text(encoding="utf-8")
        app = (PACKAGE / "www" / "app.mjs").read_text(encoding="utf-8")
        styles = (PACKAGE / "www" / "styles.css").read_text(encoding="utf-8")
        for label in [
            "Rapprocher",
            "Éloigner",
            "Annuler",
            "Rétablir",
            "Restaurer la source",
            "Surface 3D",
            "Simulation hors ligne",
        ]:
            self.assertIn(label, html)
        self.assertIn("click", app)
        self.assertNotIn("drag", app.lower())
        self.assertNotIn("pointermove", app.lower())
        self.assertIn("[hidden]", styles)
        self.assertIn("display: none !important", styles)


if __name__ == "__main__":
    unittest.main()
