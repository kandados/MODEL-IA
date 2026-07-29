
from __future__ import annotations

import cadquery as cq

from src.models.mechanical_plan import MechanicalPlan, Support


class SupportBuilder:
    """Genera soportes internos a partir de un MechanicalPlan."""

    DEFAULT_STANDOFF_DIAMETER_MM = 6.0
    DEFAULT_STANDOFF_HEIGHT_MM = 4.0
    DEFAULT_HOLE_DIAMETER_MM = 2.8

    DEFAULT_GENERIC_WIDTH_MM = 8.0
    DEFAULT_GENERIC_DEPTH_MM = 8.0
    DEFAULT_GENERIC_HEIGHT_MM = 3.0

    DEFAULT_BATTERY_WALL_MM = 1.5
    DEFAULT_DISPLAY_FRAME_MM = 2.0

    def build(self, plan: MechanicalPlan) -> cq.Workplane:
        supports = cq.Workplane("XY")

        for index, support in enumerate(plan.supports):
            support_body = self._build_support(support, index)
            supports = supports.union(support_body)

        return supports

    def _build_support(
        self,
        support: Support,
        index: int,
    ) -> cq.Workplane:
        position_x = index * 12.0
        position_y = 0.0

        if support.kind == "pcb_standoff":
            return self._build_pcb_standoffs(
                quantity=support.quantity,
                origin_x=position_x,
                origin_y=position_y,
            )

        if support.kind == "battery_holder":
            return self._build_battery_holder(
                origin_x=position_x,
                origin_y=position_y,
            )

        if support.kind == "display_frame":
            return self._build_display_frame(
                origin_x=position_x,
                origin_y=position_y,
            )

        return self._build_generic_support(
            origin_x=position_x,
            origin_y=position_y,
        )

    def _build_pcb_standoffs(
        self,
        quantity: int,
        origin_x: float,
        origin_y: float,
    ) -> cq.Workplane:
        result = cq.Workplane("XY")

        spacing = 12.0
        columns = 2

        for index in range(max(1, quantity)):
            column = index % columns
            row = index // columns

            x = origin_x + (column * spacing)
            y = origin_y + (row * spacing)

            standoff = (
                cq.Workplane("XY")
                .center(x, y)
                .circle(self.DEFAULT_STANDOFF_DIAMETER_MM / 2.0)
                .extrude(self.DEFAULT_STANDOFF_HEIGHT_MM)
                .faces(">Z")
                .workplane()
                .hole(
                    self.DEFAULT_HOLE_DIAMETER_MM,
                    self.DEFAULT_STANDOFF_HEIGHT_MM,
                )
            )

            result = result.union(standoff)

        return result

    def _build_battery_holder(
        self,
        origin_x: float,
        origin_y: float,
    ) -> cq.Workplane:
        outer_width = 42.0
        outer_depth = 24.0
        wall = self.DEFAULT_BATTERY_WALL_MM
        height = 6.0

        outer = (
            cq.Workplane("XY")
            .center(origin_x, origin_y)
            .box(
                outer_width,
                outer_depth,
                height,
                centered=(True, True, False),
            )
        )

        inner = (
            cq.Workplane("XY")
            .center(origin_x, origin_y)
            .box(
                outer_width - (2.0 * wall),
                outer_depth - (2.0 * wall),
                height,
                centered=(True, True, False),
            )
            .translate((0.0, 0.0, wall))
        )

        return outer.cut(inner)

    def _build_display_frame(
        self,
        origin_x: float,
        origin_y: float,
    ) -> cq.Workplane:
        outer_width = 50.0
        outer_depth = 34.0
        frame = self.DEFAULT_DISPLAY_FRAME_MM
        height = 3.0

        outer = (
            cq.Workplane("XY")
            .center(origin_x, origin_y)
            .box(
                outer_width,
                outer_depth,
                height,
                centered=(True, True, False),
            )
        )

        inner = (
            cq.Workplane("XY")
            .center(origin_x, origin_y)
            .box(
                outer_width - (2.0 * frame),
                outer_depth - (2.0 * frame),
                height,
                centered=(True, True, False),
            )
        )

        return outer.cut(inner)

    def _build_generic_support(
        self,
        origin_x: float,
        origin_y: float,
    ) -> cq.Workplane:
        return (
            cq.Workplane("XY")
            .center(origin_x, origin_y)
            .box(
                self.DEFAULT_GENERIC_WIDTH_MM,
                self.DEFAULT_GENERIC_DEPTH_MM,
                self.DEFAULT_GENERIC_HEIGHT_MM,
                centered=(True, True, False),
            )
        )