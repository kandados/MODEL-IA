from __future__ import annotations

import cadquery as cq

from src.cad.enclosure_specification import EnclosureSpecification
from src.cad.geometry_primitives import GeometryPrimitives
from src.models.mechanical_plan import MechanicalPlan


class EnclosureBuilder:
    """
    Genera una carcasa formada por una base hueca y una tapa independiente.

    La clase no mantiene parámetros geométricos propios. Todos los valores
    compartidos se obtienen mediante EnclosureSpecification.
    """

    BOOLEAN_TOLERANCE = 0.10

    def build(
        self,
        plan: MechanicalPlan,
    ) -> cq.Workplane:
        specification = EnclosureSpecification.from_plan(plan)

        return self._build_open_container(
            width_mm=specification.external_box.width_mm,
            depth_mm=specification.external_box.depth_mm,
            height_mm=specification.external_box.height_mm,
            wall_thickness_mm=specification.wall_thickness_mm,
            corner_radius_mm=specification.corner_radius_mm,
        )

    def build_base(
        self,
        plan: MechanicalPlan,
    ) -> cq.Workplane:
        specification = EnclosureSpecification.from_plan(plan)

        return self._build_open_container(
            width_mm=specification.external_box.width_mm,
            depth_mm=specification.external_box.depth_mm,
            height_mm=specification.base_height_mm,
            wall_thickness_mm=specification.wall_thickness_mm,
            corner_radius_mm=specification.corner_radius_mm,
        )

    def build_lid(
        self,
        plan: MechanicalPlan,
    ) -> cq.Workplane:
        specification = EnclosureSpecification.from_plan(plan)

        return self._build_downward_open_lid(
            width_mm=specification.external_box.width_mm,
            depth_mm=specification.external_box.depth_mm,
            height_mm=specification.lid_height_mm,
            wall_thickness_mm=specification.wall_thickness_mm,
            corner_radius_mm=specification.corner_radius_mm,
        )

    def _build_open_container(
        self,
        width_mm: float,
        depth_mm: float,
        height_mm: float,
        wall_thickness_mm: float,
        corner_radius_mm: float,
    ) -> cq.Workplane:
        outer_radius = self._calculate_safe_corner_radius(
            width_mm=width_mm,
            depth_mm=depth_mm,
            requested_radius_mm=corner_radius_mm,
        )

        outer = self._build_rounded_box(
            width_mm=width_mm,
            depth_mm=depth_mm,
            height_mm=height_mm,
            corner_radius_mm=outer_radius,
        )

        inner_width = width_mm - 2.0 * wall_thickness_mm
        inner_depth = depth_mm - 2.0 * wall_thickness_mm

        inner_height = (
            height_mm
            - wall_thickness_mm
            + self.BOOLEAN_TOLERANCE
        )

        inner_radius = self._calculate_inner_radius(
            outer_radius_mm=outer_radius,
            wall_thickness_mm=wall_thickness_mm,
            inner_width_mm=inner_width,
            inner_depth_mm=inner_depth,
        )

        inner = self._build_rounded_box(
            width_mm=inner_width,
            depth_mm=inner_depth,
            height_mm=inner_height,
            corner_radius_mm=inner_radius,
        )

        inner = inner.translate(
            (
                0.0,
                0.0,
                wall_thickness_mm,
            )
        )

        result = outer.cut(inner)

        self._validate_resulting_solid(
            result,
            operation_name="construcción de la base hueca",
        )

        return result

    def _build_downward_open_lid(
        self,
        width_mm: float,
        depth_mm: float,
        height_mm: float,
        wall_thickness_mm: float,
        corner_radius_mm: float,
    ) -> cq.Workplane:
        outer_radius = self._calculate_safe_corner_radius(
            width_mm=width_mm,
            depth_mm=depth_mm,
            requested_radius_mm=corner_radius_mm,
        )

        outer = self._build_rounded_box(
            width_mm=width_mm,
            depth_mm=depth_mm,
            height_mm=height_mm,
            corner_radius_mm=outer_radius,
        )

        inner_width = width_mm - 2.0 * wall_thickness_mm
        inner_depth = depth_mm - 2.0 * wall_thickness_mm

        inner_height = (
            height_mm
            - wall_thickness_mm
            + self.BOOLEAN_TOLERANCE
        )

        inner_radius = self._calculate_inner_radius(
            outer_radius_mm=outer_radius,
            wall_thickness_mm=wall_thickness_mm,
            inner_width_mm=inner_width,
            inner_depth_mm=inner_depth,
        )

        inner = self._build_rounded_box(
            width_mm=inner_width,
            depth_mm=inner_depth,
            height_mm=inner_height,
            corner_radius_mm=inner_radius,
        )

        inner = inner.translate(
            (
                0.0,
                0.0,
                -self.BOOLEAN_TOLERANCE,
            )
        )

        result = outer.cut(inner)

        self._validate_resulting_solid(
            result,
            operation_name="construcción de la tapa hueca",
        )

        return result

    def _build_rounded_box(
        self,
        width_mm: float,
        depth_mm: float,
        height_mm: float,
        corner_radius_mm: float,
    ) -> cq.Workplane:
        body = GeometryPrimitives.box(
            width_mm=width_mm,
            depth_mm=depth_mm,
            height_mm=height_mm,
        )

        if corner_radius_mm <= 0:
            return body

        return GeometryPrimitives.fillet(
            body=body,
            radius_mm=corner_radius_mm,
            edge_selector="|Z",
        )

    @staticmethod
    def _calculate_safe_corner_radius(
        width_mm: float,
        depth_mm: float,
        requested_radius_mm: float,
    ) -> float:
        shortest_side = min(
            width_mm,
            depth_mm,
        )

        maximum_radius = shortest_side * 0.20

        return max(
            0.0,
            min(
                requested_radius_mm,
                maximum_radius,
            ),
        )

    @staticmethod
    def _calculate_inner_radius(
        outer_radius_mm: float,
        wall_thickness_mm: float,
        inner_width_mm: float,
        inner_depth_mm: float,
    ) -> float:
        desired_radius = max(
            0.0,
            outer_radius_mm - wall_thickness_mm,
        )

        maximum_radius = (
            min(
                inner_width_mm,
                inner_depth_mm,
            )
            * 0.20
        )

        return min(
            desired_radius,
            maximum_radius,
        )

    @staticmethod
    def _validate_resulting_solid(
        body: cq.Workplane,
        operation_name: str,
    ) -> None:
        solid_count = body.solids().size()

        if solid_count != 1:
            raise ValueError(
                f"La {operation_name} produjo {solid_count} sólidos. "
                "Se esperaba exactamente uno."
            )

        shape = body.val()

        if shape is None:
            raise ValueError(
                f"La {operation_name} no produjo ninguna geometría."
            )

        if not shape.isValid():
            raise ValueError(
                f"La geometría resultante de la {operation_name} "
                "no es válida."
            )

        if shape.Volume() <= 0:
            raise ValueError(
                f"La geometría resultante de la {operation_name} "
                "no tiene volumen positivo."
            )