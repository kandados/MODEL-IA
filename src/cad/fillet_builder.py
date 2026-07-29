
from __future__ import annotations

import cadquery as cq

from src.models.mechanical_plan import MechanicalPlan


class FilletBuilder:
    """Aplica radios y chaflanes de forma centralizada."""

    DEFAULT_OUTER_FILLET = 2.0
    DEFAULT_INNER_FILLET = 1.0
    DEFAULT_CHAMFER = 0.6

    def apply(self, body: cq.Workplane, plan: MechanicalPlan) -> cq.Workplane:
        body = self.apply_outer_fillet(body)
        body = self.apply_inner_fillet(body)
        body = self.apply_chamfers(body)
        return body

    def apply_outer_fillet(
        self,
        body: cq.Workplane,
        radius: float | None = None,
    ) -> cq.Workplane:
        radius = radius or self.DEFAULT_OUTER_FILLET

        try:
            return body.edges("|Z").fillet(radius)
        except Exception:
            return body

    def apply_inner_fillet(
        self,
        body: cq.Workplane,
        radius: float | None = None,
    ) -> cq.Workplane:
        radius = radius or self.DEFAULT_INNER_FILLET

        try:
            return body.edges("<Z").fillet(radius)
        except Exception:
            return body

    def apply_chamfers(
        self,
        body: cq.Workplane,
        distance: float | None = None,
    ) -> cq.Workplane:
        distance = distance or self.DEFAULT_CHAMFER

        try:
            return body.edges(">Z").chamfer(distance)
        except Exception:
            return body

    def apply_custom_fillet(
        self,
        body: cq.Workplane,
        selector: str,
        radius: float,
    ) -> cq.Workplane:
        try:
            return body.edges(selector).fillet(radius)
        except Exception:
            return body

    def apply_custom_chamfer(
        self,
        body: cq.Workplane,
        selector: str,
        distance: float,
    ) -> cq.Workplane:
        try:
            return body.edges(selector).chamfer(distance)
        except Exception:
            return bodyx