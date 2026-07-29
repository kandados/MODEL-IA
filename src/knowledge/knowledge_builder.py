
from __future__ import annotations

import re
from typing import Optional

from src.models.research_report import ResearchReport, TechnicalFact
from src.models.engineering_knowledge import (
    EngineeringKnowledge,
    Identity,
    Dimensions,
    Material,
    Component,
    Port,
    Button,
    Fastener,
    Relationship,
    Constraint,
    Manufacturing,
    Reference,
)


class KnowledgeBuilder:
    """
    Convierte un ResearchReport en un EngineeringKnowledge estructurado.
    """

    def build(self, report: ResearchReport) -> EngineeringKnowledge:
        knowledge = EngineeringKnowledge(
            identity=self._extract_identity(report)
        )

        self._extract_dimensions(report, knowledge)
        self._extract_materials(report, knowledge)
        self._extract_components(report, knowledge)
        self._extract_ports(report, knowledge)
        self._extract_buttons(report, knowledge)
        self._extract_fasteners(report, knowledge)
        self._extract_constraints(report, knowledge)
        self._extract_relationships(report, knowledge)
        self._extract_manufacturing(report, knowledge)
        self._extract_references(report, knowledge)

        if report.researched_objects:
            knowledge.overall_confidence = (
                sum(o.overall_confidence for o in report.researched_objects)
                / len(report.researched_objects)
            )

        return knowledge

    def _extract_identity(self, report: ResearchReport) -> Identity:
        if not report.researched_objects:
            return Identity()

        obj = report.researched_objects[0]

        return Identity(
            manufacturer=obj.manufacturer or "",
            model=obj.model or "",
            aliases=[obj.object_name],
        )

    def _extract_dimensions(
        self,
        report: ResearchReport,
        knowledge: EngineeringKnowledge,
    ) -> None:

        for obj in report.researched_objects:
            for fact in obj.technical_facts:
                if fact.category != "dimension":
                    continue

                value = self._extract_number(fact.value)
                if value is None:
                    continue

                name = fact.name.lower()

                if "width" in name or "ancho" in name:
                    knowledge.dimensions.width_mm = value
                elif "depth" in name or "largo" in name or "length" in name:
                    knowledge.dimensions.depth_mm = value
                elif "height" in name or "alto" in name:
                    knowledge.dimensions.height_mm = value

    def _extract_materials(self, report, knowledge):
        for obj in report.researched_objects:
            for fact in obj.technical_facts:
                if fact.category == "material":
                    knowledge.materials.append(
                        Material(
                            name=fact.value,
                            confidence=fact.confidence,
                        )
                    )

    def _extract_components(self, report, knowledge):
        for obj in report.researched_objects:
            knowledge.components.append(
                Component(
                    id=obj.object_name.lower().replace(" ", "_"),
                    type="device",
                    name=obj.object_name,
                    manufacturer=obj.manufacturer,
                    model=obj.model,
                )
            )

    def _extract_ports(self, report, knowledge):
        for obj in report.researched_objects:
            for fact in obj.technical_facts:
                if fact.category == "port":
                    knowledge.ports.append(
                        Port(type=fact.name)
                    )

    def _extract_buttons(self, report, knowledge):
        for obj in report.researched_objects:
            for fact in obj.technical_facts:
                if fact.category == "button":
                    knowledge.buttons.append(
                        Button(name=fact.name)
                    )

    def _extract_fasteners(self, report, knowledge):
        for obj in report.researched_objects:
            for fact in obj.technical_facts:
                if fact.category == "mounting":
                    knowledge.fasteners.append(
                        Fastener(
                            type=fact.name,
                            quantity=1,
                        )
                    )

    def _extract_constraints(self, report, knowledge):
        for obj in report.researched_objects:
            for text in obj.unresolved_information:
                knowledge.constraints.append(
                    Constraint(
                        category="missing_information",
                        description=text,
                        critical=False,
                    )
                )

            for text in obj.contradictions:
                knowledge.constraints.append(
                    Constraint(
                        category="contradiction",
                        description=text,
                        critical=True,
                    )
                )

    def _extract_relationships(self, report, knowledge):
        return

    def _extract_manufacturing(self, report, knowledge):
        knowledge.manufacturing = Manufacturing()

    def _extract_references(self, report, knowledge):
        for obj in report.researched_objects:
            for source in obj.sources:
                knowledge.references.append(
                    Reference(
                        title=source.title,
                        source_id=source.source_id,
                        url=source.url,
                    )
                )

    @staticmethod
    def _extract_number(text: str) -> Optional[float]:
        match = re.search(r"[-+]?\d+(?:[.,]\d+)?", text)
        if not match:
            return None
        return float(match.group(0).replace(",", "."))