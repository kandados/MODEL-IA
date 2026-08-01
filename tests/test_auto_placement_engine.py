from __future__ import annotations

import unittest
from types import SimpleNamespace

from src.cad.geometric_reference_system import AxisAlignedVolume
from src.models.mechanical_plan import ComponentDimensions, MechanicalPlan
from src.planner.auto_placement_engine import (
    AutoPlacementEngine,
    AutoPlacementItem,
)


class FakeReferenceSystem:
    """
    Referencias geométricas mínimas para aislar AutoPlacementEngine.

    El motor solo necesita el volumen útil y el anclaje floor_center.
    """

    def __init__(self, usable_interior: AxisAlignedVolume) -> None:
        self.usable_interior = usable_interior
        self._floor_center = SimpleNamespace(
            x_mm=(
                usable_interior.min_x_mm
                + usable_interior.max_x_mm
            )
            / 2.0,
            y_mm=(
                usable_interior.min_y_mm
                + usable_interior.max_y_mm
            )
            / 2.0,
            z_mm=usable_interior.min_z_mm,
        )

    def get_anchor(self, anchor: str) -> SimpleNamespace:
        if anchor != "floor_center":
            raise ValueError(f"Anclaje inesperado en la prueba: {anchor}")

        return self._floor_center


class AutoPlacementEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = AutoPlacementEngine()
        self.plan = MechanicalPlan()

    def test_rotates_when_only_ninety_degrees_fits_and_preserves_z(self) -> None:
        references = FakeReferenceSystem(
            AxisAlignedVolume(
                min_x_mm=0.0,
                max_x_mm=20.0,
                min_y_mm=0.0,
                max_y_mm=14.0,
                min_z_mm=0.0,
                max_z_mm=10.0,
            )
        )
        item = AutoPlacementItem(
            target="display",
            dimensions=ComponentDimensions(
                width_mm=12.0,
                depth_mm=18.0,
                height_mm=3.0,
            ),
            clearance_mm=1.0,
            elevation_mm=2.0,
        )

        result = self.engine.place(
            self.plan,
            [item],
            references=references,
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.placed_items), 1)

        placed = result.placed_items[0]
        self.assertEqual(placed.placement.rotation_z_deg, 90.0)
        self.assertEqual(placed.placement.offset.z_mm, 3.0)
        self.assertEqual(placed.occupied_volume.min_x_mm, 0.0)
        self.assertEqual(placed.occupied_volume.max_x_mm, 20.0)
        self.assertEqual(placed.occupied_volume.min_y_mm, 0.0)
        self.assertEqual(placed.occupied_volume.max_y_mm, 14.0)
        self.assertEqual(placed.occupied_volume.min_z_mm, 2.0)
        self.assertEqual(placed.occupied_volume.max_z_mm, 7.0)

    def test_candidate_search_selects_the_more_compact_layout(self) -> None:
        references = FakeReferenceSystem(
            AxisAlignedVolume(
                min_x_mm=0.0,
                max_x_mm=30.0,
                min_y_mm=0.0,
                max_y_mm=30.0,
                min_z_mm=0.0,
                max_z_mm=10.0,
            )
        )
        items = [
            AutoPlacementItem(
                target="main_board",
                dimensions=ComponentDimensions(
                    width_mm=12.0,
                    depth_mm=12.0,
                    height_mm=2.0,
                ),
                clearance_mm=0.0,
            ),
            AutoPlacementItem(
                target="controller",
                dimensions=ComponentDimensions(
                    width_mm=10.0,
                    depth_mm=4.0,
                    height_mm=2.0,
                ),
                clearance_mm=0.0,
            ),
        ]

        result = self.engine.place(
            self.plan,
            items,
            references=references,
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.placed_items), 2)

        by_target = {
            placed.item.target: placed
            for placed in result.placed_items
        }
        main_board = by_target["main_board"]
        controller = by_target["controller"]

        self.assertEqual(controller.placement.rotation_z_deg, 90.0)
        self.assertEqual(controller.occupied_volume.min_x_mm, 14.0)
        self.assertEqual(controller.occupied_volume.max_x_mm, 18.0)
        self.assertEqual(controller.occupied_volume.min_y_mm, 0.0)
        self.assertEqual(controller.occupied_volume.max_y_mm, 10.0)
        self.assertFalse(
            self._strictly_intersect(
                main_board.occupied_volume,
                controller.occupied_volume,
            )
        )

        used_max_x_mm = max(
            placed.occupied_volume.max_x_mm
            for placed in result.placed_items
        )
        used_max_y_mm = max(
            placed.occupied_volume.max_y_mm
            for placed in result.placed_items
        )
        self.assertEqual(used_max_x_mm * used_max_y_mm, 216.0)

        for placed in result.placed_items:
            self.assertTrue(
                self._contains(
                    references.usable_interior,
                    placed.occupied_volume,
                )
            )

    def test_touching_faces_are_not_a_collision(self) -> None:
        first = AxisAlignedVolume(
            min_x_mm=0.0,
            max_x_mm=10.0,
            min_y_mm=0.0,
            max_y_mm=10.0,
            min_z_mm=0.0,
            max_z_mm=5.0,
        )
        touching = AxisAlignedVolume(
            min_x_mm=10.0,
            max_x_mm=20.0,
            min_y_mm=0.0,
            max_y_mm=10.0,
            min_z_mm=0.0,
            max_z_mm=5.0,
        )
        overlapping = AxisAlignedVolume(
            min_x_mm=9.9,
            max_x_mm=20.0,
            min_y_mm=0.0,
            max_y_mm=10.0,
            min_z_mm=0.0,
            max_z_mm=5.0,
        )

        self.assertFalse(self.engine._volumes_intersect(first, touching))
        self.assertTrue(self.engine._volumes_intersect(first, overlapping))

    def test_reports_an_issue_when_no_candidate_fits(self) -> None:
        references = FakeReferenceSystem(
            AxisAlignedVolume(
                min_x_mm=0.0,
                max_x_mm=10.0,
                min_y_mm=0.0,
                max_y_mm=10.0,
                min_z_mm=0.0,
                max_z_mm=5.0,
            )
        )
        item = AutoPlacementItem(
            target="oversized_battery",
            dimensions=ComponentDimensions(
                width_mm=20.0,
                depth_mm=12.0,
                height_mm=3.0,
            ),
            clearance_mm=1.0,
        )

        result = self.engine.place(
            self.plan,
            [item],
            references=references,
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(result.placements, [])
        self.assertEqual(result.placed_items, [])
        self.assertEqual(len(result.issues), 1)
        self.assertEqual(
            result.issues[0].code,
            "component_cannot_be_placed",
        )
        self.assertEqual(result.issues[0].target, "oversized_battery")

    @staticmethod
    def _contains(
        container: AxisAlignedVolume,
        content: AxisAlignedVolume,
    ) -> bool:
        return (
            container.min_x_mm <= content.min_x_mm
            and content.max_x_mm <= container.max_x_mm
            and container.min_y_mm <= content.min_y_mm
            and content.max_y_mm <= container.max_y_mm
            and container.min_z_mm <= content.min_z_mm
            and content.max_z_mm <= container.max_z_mm
        )

    @staticmethod
    def _strictly_intersect(
        first: AxisAlignedVolume,
        second: AxisAlignedVolume,
    ) -> bool:
        separated = (
            first.max_x_mm <= second.min_x_mm
            or second.max_x_mm <= first.min_x_mm
            or first.max_y_mm <= second.min_y_mm
            or second.max_y_mm <= first.min_y_mm
            or first.max_z_mm <= second.min_z_mm
            or second.max_z_mm <= first.min_z_mm
        )
        return not separated


if __name__ == "__main__":
    unittest.main()
