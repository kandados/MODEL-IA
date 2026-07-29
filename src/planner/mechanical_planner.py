from __future__ import annotations

from src.models.engineering_knowledge import EngineeringKnowledge
from src.models.mechanical_plan import (
    MechanicalPlan,
    BoundingBox,
    Support,
    Opening,
    MountFeature,
    Clearance,
    MechanicalDecision,
)


class MechanicalPlanner:
    """
    Convierte EngineeringKnowledge en un MechanicalPlan.
    No genera geometría CAD; únicamente decisiones mecánicas.
    """

    def build(self, knowledge: EngineeringKnowledge) -> MechanicalPlan:
        plan = MechanicalPlan()

        if (
            knowledge.dimensions.width_mm
            and knowledge.dimensions.depth_mm
            and knowledge.dimensions.height_mm
        ):
            plan.external_bounding_box = BoundingBox(
                width_mm=knowledge.dimensions.width_mm + 4.0,
                depth_mm=knowledge.dimensions.depth_mm + 4.0,
                height_mm=knowledge.dimensions.height_mm + 4.0,
            )

        for component in knowledge.components:
            plan.internal_components.append(component.id)

            ctype = component.type.lower()

            if ctype == "pcb":
                plan.supports.append(
                    Support(
                        target=component.id,
                        kind="pcb_standoff",
                        quantity=max(4, len(component.mounting_points)),
                    )
                )

            elif ctype == "battery":
                plan.supports.append(
                    Support(
                        target=component.id,
                        kind="battery_holder",
                    )
                )

            elif ctype == "display":
                plan.supports.append(
                    Support(
                        target=component.id,
                        kind="display_frame",
                    )
                )

            else:
                plan.supports.append(
                    Support(
                        target=component.id,
                        kind="generic_support",
                    )
                )

            plan.clearances.append(
                Clearance(
                    target=component.id,
                    value_mm=0.5,
                    reason="Montaje",
                )
            )

        for port in knowledge.ports:
            plan.openings.append(
                Opening(
                    target=port.type,
                    kind="port",
                    face=port.face,
                )
            )

        for button in knowledge.buttons:
            plan.openings.append(
                Opening(
                    target=button.name,
                    kind="button",
                    face=button.face,
                )
            )

        for fastener in knowledge.fasteners:
            plan.mount_features.append(
                MountFeature(
                    target=fastener.type,
                    kind="screw",
                    quantity=fastener.quantity,
                )
            )

        for constraint in knowledge.constraints:
            plan.validation_rules.append(constraint.description)

        plan.decisions.append(
            MechanicalDecision(
                category="enclosure",
                description="Diseñar una carcasa parametrizada a partir del conocimiento de ingeniería.",
            )
        )

        plan.manufacturing_notes.extend(
            knowledge.manufacturing.supported_processes
        )

        plan.overall_confidence = knowledge.overall_confidence

        return plan