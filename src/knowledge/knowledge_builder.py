from __future__ import annotations

import re
from typing import Optional

from src.models.design_request import DesignRequest
from src.models.engineering_knowledge import (
    Button,
    Component,
    Constraint,
    Dimensions,
    EngineeringKnowledge,
    Fastener,
    Identity,
    Manufacturing,
    Material,
    Port,
    Reference,
)
from src.models.research_report import ResearchReport


class KnowledgeBuilder:
    """
    Construye EngineeringKnowledge combinando:

    1. La información explícita proporcionada por el usuario.
    2. La información obtenida mediante investigación web, cuando exista.

    El DesignRequest es siempre la fuente principal de intención y requisitos.
    El ResearchReport es opcional y se utiliza para completar datos técnicos.
    """

    DIMENSION_ALIASES: dict[str, str] = {
        "width": "width_mm",
        "ancho": "width_mm",
        "x": "width_mm",
        "depth": "depth_mm",
        "length": "depth_mm",
        "largo": "depth_mm",
        "fondo": "depth_mm",
        "y": "depth_mm",
        "height": "height_mm",
        "alto": "height_mm",
        "altura": "height_mm",
        "z": "height_mm",
    }

    def build(
        self,
        design_request: DesignRequest,
        report: ResearchReport | None = None,
    ) -> EngineeringKnowledge:
        """
        Construye el conocimiento de ingeniería consolidado.

        Args:
            design_request:
                Interpretación estructurada de la petición del usuario.

            report:
                Informe de investigación opcional. Debe ser None cuando la
                petición pueda resolverse únicamente con los datos aportados
                por el usuario.

        Returns:
            EngineeringKnowledge listo para el MechanicalPlanner.
        """

        knowledge = EngineeringKnowledge(
            identity=self._extract_identity(
                design_request=design_request,
                report=report,
            )
        )

        self._extract_design_request_dimensions(
            design_request=design_request,
            knowledge=knowledge,
        )

        self._extract_design_request_requirements(
            design_request=design_request,
            knowledge=knowledge,
        )

        self._extract_design_request_objects(
            design_request=design_request,
            knowledge=knowledge,
        )

        if report is not None:
            self._extract_research_dimensions(
                report=report,
                knowledge=knowledge,
            )
            self._extract_research_materials(
                report=report,
                knowledge=knowledge,
            )
            self._extract_research_components(
                report=report,
                knowledge=knowledge,
            )
            self._extract_research_ports(
                report=report,
                knowledge=knowledge,
            )
            self._extract_research_buttons(
                report=report,
                knowledge=knowledge,
            )
            self._extract_research_fasteners(
                report=report,
                knowledge=knowledge,
            )
            self._extract_research_constraints(
                report=report,
                knowledge=knowledge,
            )
            self._extract_references(
                report=report,
                knowledge=knowledge,
            )
            self._set_research_confidence(
                report=report,
                knowledge=knowledge,
            )
        else:
            knowledge.overall_confidence = self._calculate_request_confidence(
                design_request
            )

        self._configure_manufacturing(
            design_request=design_request,
            knowledge=knowledge,
        )

        return knowledge

    def _extract_identity(
        self,
        design_request: DesignRequest,
        report: ResearchReport | None,
    ) -> Identity:
        """
        Obtiene la identidad principal del objeto.

        Se da prioridad a la información investigada cuando existe un objeto
        comercial real. En ausencia de investigación, se usa la petición.
        """

        if report is not None and report.researched_objects:
            researched_object = report.researched_objects[0]

            return Identity(
                manufacturer=researched_object.manufacturer or "",
                model=researched_object.model or "",
                aliases=[researched_object.object_name],
            )

        if design_request.identified_objects:
            identified_object = design_request.identified_objects[0]

            return Identity(
                manufacturer=identified_object.manufacturer or "",
                model=identified_object.model or "",
                aliases=[identified_object.name],
            )

        return Identity(
            aliases=[design_request.design_intent],
        )

    def _extract_design_request_dimensions(
        self,
        design_request: DesignRequest,
        knowledge: EngineeringKnowledge,
    ) -> None:
        """
        Extrae las dimensiones indicadas directamente por el usuario.

        Las dimensiones principales se almacenan en Dimensions. Las demás,
        como espesor de pared o diámetros, se conservan como restricciones
        numéricas para que el MechanicalPlanner pueda utilizarlas.
        """

        for dimension in design_request.explicit_dimensions_mm:
            normalized_name = self._normalize_dimension_name(dimension.name)
            target_field = self.DIMENSION_ALIASES.get(normalized_name)

            if target_field is not None:
                setattr(
                    knowledge.dimensions,
                    target_field,
                    dimension.value_mm,
                )
                continue

            knowledge.constraints.append(
                Constraint(
                    category="explicit_dimension",
                    description=(
                        f"{dimension.name} = {dimension.value_mm} mm"
                    ),
                    critical=True,
                    value=dimension.value_mm,
                    unit="mm",
                )
            )

    def _extract_design_request_requirements(
        self,
        design_request: DesignRequest,
        knowledge: EngineeringKnowledge,
    ) -> None:
        """
        Conserva todos los requisitos explícitos del usuario.

        También identifica cantidades de soportes, tornillos o fijaciones
        cuando pueden deducirse claramente del texto.
        """

        for requirement in design_request.explicit_requirements:
            knowledge.constraints.append(
                Constraint(
                    category="explicit_requirement",
                    description=requirement,
                    critical=True,
                )
            )

            quantity = self._extract_quantity(requirement)
            normalized_requirement = requirement.lower()

            if self._is_mounting_requirement(normalized_requirement):
                knowledge.fasteners.append(
                    Fastener(
                        type=self._classify_mounting_feature(
                            normalized_requirement
                        ),
                        quantity=quantity or 1,
                    )
                )

        for missing_decision in design_request.missing_user_decisions:
            knowledge.constraints.append(
                Constraint(
                    category="missing_user_decision",
                    description=missing_decision,
                    critical=False,
                )
            )

    def _extract_design_request_objects(
        self,
        design_request: DesignRequest,
        knowledge: EngineeringKnowledge,
    ) -> None:
        """
        Añade los objetos identificados en la petición como componentes.
        """

        existing_ids = {component.id for component in knowledge.components}

        for identified_object in design_request.identified_objects:
            component_id = self._safe_identifier(identified_object.name)

            if component_id in existing_ids:
                continue

            knowledge.components.append(
                Component(
                    id=component_id,
                    type=identified_object.object_type,
                    name=identified_object.name,
                    manufacturer=identified_object.manufacturer,
                    model=identified_object.model,
                )
            )

            existing_ids.add(component_id)

    def _extract_research_dimensions(
        self,
        report: ResearchReport,
        knowledge: EngineeringKnowledge,
    ) -> None:
        """
        Completa únicamente las dimensiones principales que todavía no
        hayan sido proporcionadas explícitamente por el usuario.
        """

        for researched_object in report.researched_objects:
            for fact in researched_object.technical_facts:
                if fact.category != "dimension":
                    continue

                value = self._extract_number(fact.value)

                if value is None:
                    continue

                normalized_name = self._normalize_dimension_name(fact.name)
                target_field = self._resolve_dimension_field(normalized_name)

                if target_field is None:
                    continue

                current_value = getattr(knowledge.dimensions, target_field)

                if current_value is None:
                    setattr(
                        knowledge.dimensions,
                        target_field,
                        value,
                    )

    def _extract_research_materials(
        self,
        report: ResearchReport,
        knowledge: EngineeringKnowledge,
    ) -> None:
        existing_materials = {
            material.name.strip().lower()
            for material in knowledge.materials
        }

        for researched_object in report.researched_objects:
            for fact in researched_object.technical_facts:
                if fact.category != "material":
                    continue

                material_name = fact.value.strip()

                if not material_name:
                    continue

                normalized_material = material_name.lower()

                if normalized_material in existing_materials:
                    continue

                knowledge.materials.append(
                    Material(
                        name=material_name,
                        confidence=fact.confidence,
                    )
                )

                existing_materials.add(normalized_material)

    def _extract_research_components(
        self,
        report: ResearchReport,
        knowledge: EngineeringKnowledge,
    ) -> None:
        existing_ids = {component.id for component in knowledge.components}

        for researched_object in report.researched_objects:
            component_id = self._safe_identifier(
                researched_object.object_name
            )

            if component_id in existing_ids:
                continue

            knowledge.components.append(
                Component(
                    id=component_id,
                    type="device",
                    name=researched_object.object_name,
                    manufacturer=researched_object.manufacturer,
                    model=researched_object.model,
                )
            )

            existing_ids.add(component_id)

    def _extract_research_ports(
        self,
        report: ResearchReport,
        knowledge: EngineeringKnowledge,
    ) -> None:
        for researched_object in report.researched_objects:
            for fact in researched_object.technical_facts:
                if fact.category == "port":
                    knowledge.ports.append(
                        Port(
                            type=fact.name,
                        )
                    )

    def _extract_research_buttons(
        self,
        report: ResearchReport,
        knowledge: EngineeringKnowledge,
    ) -> None:
        for researched_object in report.researched_objects:
            for fact in researched_object.technical_facts:
                if fact.category == "button":
                    knowledge.buttons.append(
                        Button(
                            name=fact.name,
                        )
                    )

    def _extract_research_fasteners(
        self,
        report: ResearchReport,
        knowledge: EngineeringKnowledge,
    ) -> None:
        for researched_object in report.researched_objects:
            for fact in researched_object.technical_facts:
                if fact.category != "mounting":
                    continue

                quantity = self._extract_quantity(fact.value)

                knowledge.fasteners.append(
                    Fastener(
                        type=fact.name,
                        quantity=quantity or 1,
                    )
                )

    def _extract_research_constraints(
        self,
        report: ResearchReport,
        knowledge: EngineeringKnowledge,
    ) -> None:
        for researched_object in report.researched_objects:
            for unresolved_information in (
                researched_object.unresolved_information
            ):
                knowledge.constraints.append(
                    Constraint(
                        category="missing_information",
                        description=unresolved_information,
                        critical=False,
                    )
                )

            for contradiction in researched_object.contradictions:
                knowledge.constraints.append(
                    Constraint(
                        category="contradiction",
                        description=contradiction,
                        critical=True,
                    )
                )

    def _extract_references(
        self,
        report: ResearchReport,
        knowledge: EngineeringKnowledge,
    ) -> None:
        existing_references: set[tuple[str, str | None]] = set()

        for researched_object in report.researched_objects:
            for source in researched_object.sources:
                reference_key = (
                    source.title,
                    source.url,
                )

                if reference_key in existing_references:
                    continue

                knowledge.references.append(
                    Reference(
                        title=source.title,
                        source_id=source.source_id,
                        url=source.url,
                    )
                )

                existing_references.add(reference_key)

    def _set_research_confidence(
        self,
        report: ResearchReport,
        knowledge: EngineeringKnowledge,
    ) -> None:
        if not report.researched_objects:
            knowledge.overall_confidence = 0.75
            return

        knowledge.overall_confidence = (
            sum(
                researched_object.overall_confidence
                for researched_object in report.researched_objects
            )
            / len(report.researched_objects)
        )

    def _configure_manufacturing(
        self,
        design_request: DesignRequest,
        knowledge: EngineeringKnowledge,
    ) -> None:
        """
        Establece el proceso de fabricación adecuado para la generación CAD
        actual de Model-IA.
        """

        knowledge.manufacturing = Manufacturing(
            supported_processes=[
                "FDM 3D printing",
                "SLA 3D printing",
                "CNC machining",
            ],
            preferred_process="FDM 3D printing",
        )

        knowledge.constraints.append(
            Constraint(
                category="design_intent",
                description=design_request.design_intent,
                critical=True,
            )
        )

        knowledge.constraints.append(
            Constraint(
                category="requested_output",
                description=", ".join(design_request.requested_output),
                critical=False,
            )
        )

    @staticmethod
    def _normalize_dimension_name(name: str) -> str:
        normalized = name.strip().lower()
        normalized = normalized.replace("-", "_")
        normalized = normalized.replace(" ", "_")

        if normalized.endswith("_mm"):
            normalized = normalized[:-3]

        return normalized

    def _resolve_dimension_field(
        self,
        normalized_name: str,
    ) -> str | None:
        direct_match = self.DIMENSION_ALIASES.get(normalized_name)

        if direct_match is not None:
            return direct_match

        if "width" in normalized_name or "ancho" in normalized_name:
            return "width_mm"

        if (
            "depth" in normalized_name
            or "length" in normalized_name
            or "largo" in normalized_name
            or "fondo" in normalized_name
        ):
            return "depth_mm"

        if (
            "height" in normalized_name
            or "alto" in normalized_name
            or "altura" in normalized_name
        ):
            return "height_mm"

        return None

    @staticmethod
    def _calculate_request_confidence(
        design_request: DesignRequest,
    ) -> float:
        """
        Calcula una confianza básica para peticiones sin investigación.

        Una petición con las tres dimensiones exteriores y sin decisiones
        pendientes dispone de suficiente información para generar una primera
        geometría mecánica determinista.
        """

        dimension_names = {
            KnowledgeBuilder._normalize_dimension_name(dimension.name)
            for dimension in design_request.explicit_dimensions_mm
        }

        has_width = bool(
            dimension_names.intersection({"width", "ancho", "x"})
        )
        has_depth = bool(
            dimension_names.intersection(
                {"depth", "length", "largo", "fondo", "y"}
            )
        )
        has_height = bool(
            dimension_names.intersection(
                {"height", "alto", "altura", "z"}
            )
        )

        score = 0.55

        if has_width:
            score += 0.10

        if has_depth:
            score += 0.10

        if has_height:
            score += 0.10

        if design_request.explicit_requirements:
            score += 0.05

        if not design_request.missing_user_decisions:
            score += 0.10

        return min(score, 1.0)

    @staticmethod
    def _is_mounting_requirement(text: str) -> bool:
        keywords = (
            "soporte",
            "soportes",
            "poste",
            "postes",
            "separador",
            "separadores",
            "tornillo",
            "tornillos",
            "fijación",
            "fijaciones",
            "mount",
            "mounting",
            "standoff",
            "standoffs",
            "screw",
            "screws",
        )

        return any(keyword in text for keyword in keywords)

    @staticmethod
    def _classify_mounting_feature(text: str) -> str:
        if any(
            keyword in text
            for keyword in (
                "soporte",
                "soportes",
                "poste",
                "postes",
                "separador",
                "separadores",
                "standoff",
                "standoffs",
            )
        ):
            return "pcb_standoff"

        if any(
            keyword in text
            for keyword in (
                "tornillo",
                "tornillos",
                "screw",
                "screws",
            )
        ):
            return "screw"

        return "mounting_feature"

    @staticmethod
    def _safe_identifier(value: str) -> str:
        normalized = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            value.strip(),
        )
        normalized = normalized.strip("_").lower()

        return normalized or "component"

    @staticmethod
    def _extract_quantity(text: str) -> Optional[int]:
        """
        Extrae una cantidad asociándola preferentemente al elemento mecánico.
        """

        word_numbers = {
            "un": 1, "una": 1, "uno": 1,
            "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
            "seis": 6, "siete": 7, "ocho": 8, "nueve": 9, "diez": 10,
            "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
        }

        mounting_terms = {
            "soporte","soportes","poste","postes",
            "separador","separadores","tornillo","tornillos",
            "fijacion","fijaciones","fijación",
            "mount","mounts","mounting",
            "standoff","standoffs","screw","screws",
        }

        tokens = re.findall(r"\d+|[a-záéíóúüñ]+", text.lower())

        def token_quantity(token: str) -> Optional[int]:
            if token.isdigit():
                return int(token)
            return word_numbers.get(token)

        for index, token in enumerate(tokens):
            if token not in mounting_terms:
                continue

            for i in range(max(0, index-3), index):
                q = token_quantity(tokens[i])
                if q is not None:
                    return q

            for i in range(index+1, min(len(tokens), index+4)):
                q = token_quantity(tokens[i])
                if q is not None:
                    return q

        for token in tokens:
            q = token_quantity(token)
            if q is not None:
                return q

        return None

    @staticmethod
    def _extract_number(text: str) -> Optional[float]:
        match = re.search(
            r"[-+]?\d+(?:[.,]\d+)?",
            text,
        )

        if not match:
            return None

        return float(
            match.group(0).replace(",", ".")
        )                                                                                                      
