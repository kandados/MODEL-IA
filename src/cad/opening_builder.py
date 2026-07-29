
from __future__ import annotations

import cadquery as cq

from src.models.mechanical_plan import MechanicalPlan, Opening


class OpeningBuilder:
    """Genera huecos para puertos, botones, altavoces y ventilación."""

    DEFAULT_DEPTH = 20.0

    def build(self, plan: MechanicalPlan) -> cq.Workplane:
        body = cq.Workplane("XY")

        for index, opening in enumerate(plan.openings):
            body = body.union(self._build_opening(opening, index))

        return body

    def _build_opening(
        self,
        opening: Opening,
        index: int,
    ) -> cq.Workplane:
        x = index * 12.0
        y = 0.0

        if opening.kind == "button":
            width, height = 8.0, 4.0
        elif opening.kind == "speaker":
            width, height = 18.0, 6.0
        elif opening.kind == "ventilation":
            width, height = 20.0, 3.0
        else:
            width, height = 12.0, 6.0

        return (
            cq.Workplane("XY")
            .center(x, y)
            .box(
                width,
                self.DEFAULT_DEPTH,
                height,
                centered=(True, True, True),
            )
        )