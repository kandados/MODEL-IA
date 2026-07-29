
from __future__ import annotations

import cadquery as cq

from src.models.mechanical_plan import MechanicalPlan, MountFeature


class FasteningBuilder:
    """Genera geometría de fijación a partir de mount_features."""

    DEFAULT_INSERT_DIAMETER_MM = 4.6
    DEFAULT_INSERT_HEIGHT_MM = 5.0
    DEFAULT_SCREW_POST_DIAMETER_MM = 6.0
    DEFAULT_SCREW_HOLE_DIAMETER_MM = 3.2
    DEFAULT_SCREW_POST_HEIGHT_MM = 6.0
    DEFAULT_MAGNET_DIAMETER_MM = 6.0
    DEFAULT_MAGNET_HEIGHT_MM = 2.0
    DEFAULT_CLIP_WIDTH_MM = 8.0
    DEFAULT_CLIP_DEPTH_MM = 2.5
    DEFAULT_CLIP_HEIGHT_MM = 4.0
    DEFAULT_SPACING_MM = 15.0

    def build(self, plan: MechanicalPlan) -> cq.Workplane:
        result = cq.Workplane("XY")

        for feature_index, feature in enumerate(plan.mount_features):
            feature_body = self._build_feature(feature, feature_index)
            if self._contains_shape(feature_body):
                result = result.union(feature_body)

        return result

    def _build_feature(
        self,
        feature: MountFeature,
        feature_index: int,
    ) -> cq.Workplane:
        result = cq.Workplane("XY")
        quantity = max(1, feature.quantity)

        for item_index in range(quantity):
            x = (feature_index * quantity + item_index) * self.DEFAULT_SPACING_MM
            y = 0.0

            item = self._build_single(feature.kind, x, y)
            if self._contains_shape(item):
                result = result.union(item)

        return result

    def _build_single(
        self,
        kind: str,
        x: float,
        y: float,
    ) -> cq.Workplane:
        if kind == "heat_insert":
            return self._heat_insert_post(x, y)

        if kind == "screw":
            return self._screw_post(x, y)

        if kind == "magnet":
            return self._magnet_socket(x, y)

        if kind == "snap_fit":
            return self._snap_fit_clip(x, y)

        if kind == "adhesive":
            return self._adhesive_pad(x, y)

        return cq.Workplane("XY")

    def _heat_insert_post(self, x: float, y: float) -> cq.Workplane:
        outer_diameter = self.DEFAULT_INSERT_DIAMETER_MM + 3.0

        post = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(outer_diameter / 2.0)
            .extrude(self.DEFAULT_INSERT_HEIGHT_MM)
        )

        socket = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(self.DEFAULT_INSERT_DIAMETER_MM / 2.0)
            .extrude(self.DEFAULT_INSERT_HEIGHT_MM)
        )

        return post.cut(socket)

    def _screw_post(self, x: float, y: float) -> cq.Workplane:
        post = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(self.DEFAULT_SCREW_POST_DIAMETER_MM / 2.0)
            .extrude(self.DEFAULT_SCREW_POST_HEIGHT_MM)
        )

        hole = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(self.DEFAULT_SCREW_HOLE_DIAMETER_MM / 2.0)
            .extrude(self.DEFAULT_SCREW_POST_HEIGHT_MM)
        )

        return post.cut(hole)

    def _magnet_socket(self, x: float, y: float) -> cq.Workplane:
        outer_diameter = self.DEFAULT_MAGNET_DIAMETER_MM + 2.0

        holder = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(outer_diameter / 2.0)
            .extrude(self.DEFAULT_MAGNET_HEIGHT_MM + 1.0)
        )

        socket = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(self.DEFAULT_MAGNET_DIAMETER_MM / 2.0)
            .extrude(self.DEFAULT_MAGNET_HEIGHT_MM)
            .translate((0.0, 0.0, 1.0))
        )

        return holder.cut(socket)

    def _snap_fit_clip(self, x: float, y: float) -> cq.Workplane:
        return (
            cq.Workplane("XY")
            .center(x, y)
            .box(
                self.DEFAULT_CLIP_WIDTH_MM,
                self.DEFAULT_CLIP_DEPTH_MM,
                self.DEFAULT_CLIP_HEIGHT_MM,
                centered=(True, True, False),
            )
        )

    def _adhesive_pad(self, x: float, y: float) -> cq.Workplane:
        return (
            cq.Workplane("XY")
            .center(x, y)
            .box(12.0, 12.0, 0.8, centered=(True, True, False))
        )

    @staticmethod
    def _contains_shape(workplane: cq.Workplane) -> bool:
        try:
            return any(isinstance(value, cq.Shape) for value in workplane.vals())
        except Exception:
            return False