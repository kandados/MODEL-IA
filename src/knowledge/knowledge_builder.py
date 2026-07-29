from __future__ import annotations

from src.models.engineering_knowledge import (
    Button,
    Constraint,
    Dimensions,
    EngineeringKnowledge,
    Material,
    Port,
    Ventilation,
)
from src.models.research_report import ResearchReport


class KnowledgeBuilder:
    """
    Convierte un ResearchReport en un EngineeringKnowledge.
    """

    def build(self, report: ResearchReport) -> EngineeringKnowledge:
        obj = report.researched_objects[0]

        knowledge = EngineeringKnowledge(
            manufacturer=obj.manufacturer,
            model=obj.model,
            overall_confidence=obj.overall_confidence,
        )

        for fact in obj.technical_facts:

            category = fact.category.lower()

            # ----------------------------
            # DIMENSIONES
            # ----------------------------

            if category == "dimension":
                value = fact.value.lower()

                numbers = self._extract_numbers(value)

                if len(numbers) >= 3:
                    knowledge.dimensions = Dimensions(
                        width_mm=numbers[0],
                        depth_mm=numbers[1],
                        height_mm=numbers[2],
                    )

            # ----------------------------
            # PESO
            # ----------------------------

            elif category == "weight":

                numbers = self._extract_numbers(fact.value)

                if numbers:
                    knowledge.dimensions.weight_kg = numbers[0]

            # ----------------------------
            # MATERIAL
            # ----------------------------

            elif category == "material":

                knowledge.materials.append(
                    Material(
                        name=fact.value,
                        confidence=fact.confidence,
                    )
                )

            # ----------------------------
            # PUERTOS
            # ----------------------------

            elif category == "port":

                knowledge.ports.append(
                    Port(
                        type=fact.name,
                        coordinates_known=False,
                    )
                )

            # ----------------------------
            # BOTONES
            # ----------------------------

            elif category == "button":

                knowledge.buttons.append(
                    Button(
                        name=fact.name,
                        coordinates_known=False,
                    )
                )

            # ----------------------------
            # VENTILACIÓN
            # ----------------------------

            elif category == "ventilation":

                text = fact.value.lower()

                if "below" in text or "debajo" in text:
                    knowledge.ventilation.bottom_airflow = True

                if "rear" in text or "trasera" in text:
                    knowledge.ventilation.rear_airflow = True

            # ----------------------------
            # RESTRICCIONES
            # ----------------------------

            if "no bloquear" in fact.value.lower():

                knowledge.constraints.append(
                    Constraint(
                        description=fact.value,
                        critical=True,
                    )
                )

        return knowledge

    @staticmethod
    def _extract_numbers(text: str) -> list[float]:
        import re

        values = re.findall(r"\d+(?:\.\d+)?", text)

        return [float(v) for v in values]