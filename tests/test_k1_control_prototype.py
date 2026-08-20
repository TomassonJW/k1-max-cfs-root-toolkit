import json
import unittest
from pathlib import Path

from prototype.control_state import (
    MachineContext,
    MeshCatalog,
    MeshProfile,
    ProductionBlocked,
    TemperatureController,
    ZCalibrationController,
)
from prototype.moonraker_simulator import MoonrakerSimulation, create_server


ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "prototype" / "k1-control"


def context(*, probe_revision: str = "probe-7", plate_id: str = "plate-a") -> MachineContext:
    return MachineContext(
        plate_id=plate_id,
        bed_temperature_band_c="55-65",
        nozzle_id="unicorn-a",
        nozzle_diameter_mm=0.4,
        probe_reference_revision=probe_revision,
        relevant_config_hashes={"homing": "aaa", "probe": "bbb"},
    )


class ZCalibrationStateTests(unittest.TestCase):
    def accepted_controller(self) -> tuple[ZCalibrationController, MachineContext]:
        current = context()
        controller = ZCalibrationController()
        controller.start_session(current, seed_offset_mm=0.25)
        controller.adjust(0.06)
        controller.commit(accepted_at="2026-08-20T12:00:00+00:00")
        return controller, current

    def test_live_adjustment_is_not_committed_implicitly(self) -> None:
        controller, current = self.accepted_controller()
        accepted_before = controller.accepted
        controller.start_session(current, seed_offset_mm=accepted_before.offset_mm)
        controller.adjust(0.01)
        self.assertEqual(controller.accepted, accepted_before)
        controller.cancel()
        self.assertEqual(controller.production_offset(current), 0.31)

    def test_explicit_commit_survives_end_and_restart(self) -> None:
        controller, current = self.accepted_controller()
        controller.on_print_end()
        controller.on_restart()
        self.assertEqual(controller.production_offset(current), 0.31)

    def test_new_reference_invalidates_without_deleting_history(self) -> None:
        controller, current = self.accepted_controller()
        accepted_before = controller.accepted
        controller.invalidate("new probe reference calibration")
        with self.assertRaisesRegex(ProductionBlocked, "new probe reference"):
            controller.production_offset(current)
        self.assertEqual(controller.accepted, accepted_before)

    def test_context_signature_change_blocks_stale_z(self) -> None:
        controller, _ = self.accepted_controller()
        with self.assertRaisesRegex(ProductionBlocked, "does not match"):
            controller.production_offset(context(probe_revision="probe-8"))

    def test_no_session_means_no_live_adjustment_or_commit(self) -> None:
        controller = ZCalibrationController()
        with self.assertRaises(ValueError):
            controller.adjust(0.01)
        with self.assertRaises(ValueError):
            controller.commit()


class MeshStateTests(unittest.TestCase):
    def test_reference_mesh_requires_plate_temperature_and_probe_match(self) -> None:
        current = context()
        catalog = MeshCatalog(
            profiles=[
                MeshProfile(
                    profile_id="plate-a__55-65__probe-7",
                    plate_id="plate-a",
                    bed_temperature_band_c="55-65",
                    probe_reference_revision="probe-7",
                )
            ]
        )
        self.assertEqual(catalog.reference_for(current).profile_id, "plate-a__55-65__probe-7")
        with self.assertRaises(ProductionBlocked):
            catalog.reference_for(context(plate_id="plate-b"))

    def test_adaptive_mesh_is_never_persisted(self) -> None:
        decision = MeshCatalog().adaptive_for((15.0, 20.0, 180.0, 190.0))
        self.assertEqual(decision.mode, "adaptive")
        self.assertFalse(decision.persist_after_job)


class TemperatureOwnershipTests(unittest.TestCase):
    def test_equivalent_refill_preserves_active_target(self) -> None:
        controller = TemperatureController({0: 205.0, 1: 220.0})
        self.assertEqual(controller.start_initial_tool(0), 205.0)
        self.assertEqual(controller.equivalent_refill(), 205.0)
        matches, correction = controller.check_cfs_write(220.0)
        self.assertFalse(matches)
        self.assertEqual(correction, 205.0)

    def test_intentional_change_uses_next_tool_target(self) -> None:
        controller = TemperatureController({0: 205.0, 1: 220.0})
        controller.start_initial_tool(0)
        self.assertEqual(controller.intentional_tool_change(1), 220.0)

    def test_operator_target_remains_until_next_explicit_gcode_target(self) -> None:
        controller = TemperatureController({0: 205.0})
        controller.start_initial_tool(0)
        controller.operator_change(198.0)
        self.assertEqual(controller.equivalent_refill(), 198.0)
        self.assertEqual(controller.owner, "operator")
        controller.gcode_change(0, 210.0)
        self.assertEqual(controller.expected_target_c, 210.0)
        self.assertEqual(controller.owner, "gcode")


class StaticInterfaceTests(unittest.TestCase):
    def test_interface_uses_only_the_relative_simulated_moonraker_adapter(self) -> None:
        html = (UI / "index.html").read_text(encoding="utf-8")
        javascript = (UI / "app-moonraker.js").read_text(encoding="utf-8")
        adapter = (UI / "moonraker-adapter.js").read_text(encoding="utf-8")
        self.assertIn('data-mode="simulation"', html)
        self.assertIn("Simulation locale", html)
        self.assertIn('type="module"', html)
        self.assertIn("/server/info", adapter)
        self.assertIn("/printer/objects/query", adapter)
        self.assertIn("/printer/gcode/script", adapter)
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("WebSocket", javascript)
        self.assertNotIn("http://", adapter)
        self.assertNotIn("https://", adapter)

    def test_mock_state_is_synthetic_and_shows_the_product_contract(self) -> None:
        state = json.loads((UI / "mock-state.json").read_text(encoding="utf-8"))
        self.assertTrue(state["simulation"])
        self.assertEqual(state["calibration"]["status"], "accepted")
        self.assertFalse(state["mesh"]["persistAfterJob"])
        self.assertEqual(state["temperature"]["owner"], "G-code")
        self.assertEqual(
            [stage["id"] for stage in state["sequence"][-2:]],
            ["cfs", "print"],
        )
        self.assertTrue(all(stage["status"] == "locked" for stage in state["sequence"][-2:]))

    def test_simulated_moonraker_applies_the_python_z_state_rules(self) -> None:
        simulation = MoonrakerSimulation()
        before = simulation.snapshot()["calibration"]["offsetMm"]
        simulation.dispatch_script(f"K1_Z_SESSION_START SEED={before}")
        simulation.dispatch_script("K1_Z_ADJUST DELTA=0.005")
        provisional = simulation.snapshot()
        self.assertEqual(provisional["calibration"]["offsetMm"], before)
        self.assertAlmostEqual(provisional["calibration"]["session"]["currentOffsetMm"], before + 0.005)
        simulation.dispatch_script("K1_Z_COMMIT")
        committed = simulation.snapshot()
        self.assertAlmostEqual(committed["calibration"]["offsetMm"], before + 0.005)
        self.assertTrue(committed["calibration"]["canRestore"])
        simulation.dispatch_script("K1_SIM_RESTART")
        self.assertAlmostEqual(simulation.snapshot()["calibration"]["offsetMm"], before + 0.005)
        simulation.dispatch_script("K1_SIM_REFERENCE_CALIBRATION")
        self.assertFalse(simulation.snapshot()["ready"])

    def test_simulator_binds_only_to_loopback(self) -> None:
        server = create_server(0)
        try:
            self.assertEqual(server.server_address[0], "127.0.0.1")
        finally:
            server.server_close()


if __name__ == "__main__":
    unittest.main()
