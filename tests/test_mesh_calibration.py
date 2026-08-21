import unittest

from prototype.mesh_calibration import (
    MeshPlanRejected,
    compare_repeated_meshes,
    plan_mesh_calibration,
    plan_mesh_preset,
    summarize_mesh,
)


CONTEXT = {
    "plate_id": "PLATE_A",
    "temperature_band_c": "PLA_50_60",
    "probe_reference_revision": "PRTOUCH_R1",
}


class MeshPlanningTests(unittest.TestCase):
    def test_current_quick_preset_matches_the_captured_six_by_six_shape(self) -> None:
        plan = plan_mesh_preset("quick", mode="reference", **CONTEXT)
        self.assertEqual(plan.probe_count, (6, 6))
        self.assertEqual(plan.point_count, 36)
        self.assertEqual(plan.spacing_mm, (58.0, 58.0))
        self.assertEqual(plan.algorithm, "lagrange")
        self.assertTrue(plan.persist_after_calibration)

    def test_precise_preset_uses_real_points_and_bicubic_interpolation(self) -> None:
        plan = plan_mesh_preset("precise", mode="reference", **CONTEXT)
        self.assertEqual(plan.probe_count, (11, 11))
        self.assertEqual(plan.point_count, 121)
        self.assertEqual(plan.spacing_mm, (29.0, 29.0))
        self.assertEqual(plan.algorithm, "bicubic")
        self.assertEqual(
            plan.profile_name,
            "K1_PLATE_A_PLA_50_60_PRTOUCH_R1_11X11",
        )
        self.assertEqual(plan.moonraker_parameters()["PROBE_COUNT"], "11,11")

    def test_adaptive_plan_is_bounded_and_never_persistent(self) -> None:
        plan = plan_mesh_calibration(
            mode="adaptive",
            probe_count=(5, 7),
            bounds_mm=(50.0, 60.0, 150.0, 180.0),
            **CONTEXT,
        )
        self.assertEqual(plan.spacing_mm, (25.0, 20.0))
        self.assertEqual(plan.profile_name, "K1_ADAPTIVE_RUNTIME")
        self.assertFalse(plan.persist_after_calibration)

    def test_out_of_bounds_or_unbounded_density_is_rejected(self) -> None:
        with self.assertRaisesRegex(MeshPlanRejected, "probe area"):
            plan_mesh_calibration(
                mode="reference",
                probe_count=(11, 11),
                bounds_mm=(0.0, 5.0, 295.0, 295.0),
                **CONTEXT,
            )
        with self.assertRaisesRegex(MeshPlanRejected, "between 3 and 25"):
            plan_mesh_calibration(
                mode="reference",
                probe_count=(26, 11),
                **CONTEXT,
            )


class MeshQualificationTests(unittest.TestCase):
    def test_summary_uses_measured_points_not_interpolated_points(self) -> None:
        summary = summarize_mesh(((0.10, 0.15), (-0.05, 0.20)))
        self.assertEqual((summary.rows, summary.columns), (2, 2))
        self.assertAlmostEqual(summary.minimum_mm, -0.05)
        self.assertAlmostEqual(summary.maximum_mm, 0.20)
        self.assertAlmostEqual(summary.range_mm, 0.25)

    def test_repeated_mesh_is_accepted_only_inside_the_tolerance(self) -> None:
        first = ((0.100, 0.200), (0.300, 0.400))
        close = ((0.110, 0.190), (0.315, 0.390))
        drifting = ((0.100, 0.200), (0.340, 0.400))
        accepted = compare_repeated_meshes(first, close)
        rejected = compare_repeated_meshes(first, drifting)
        self.assertTrue(accepted.accepted)
        self.assertEqual(accepted.compared_points, 4)
        self.assertFalse(rejected.accepted)
        self.assertAlmostEqual(rejected.maximum_delta_mm, 0.04)

    def test_mismatched_shapes_are_rejected(self) -> None:
        with self.assertRaisesRegex(MeshPlanRejected, "different dimensions"):
            compare_repeated_meshes(((0.0, 0.1),), ((0.0,),))


if __name__ == "__main__":
    unittest.main()
