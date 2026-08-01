from __future__ import annotations

import unicodedata

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

    No genera geometría CAD. Únicamente transforma el conocimiento
    de ingeniería en decisiones mecánicas estructuradas.
    """

    def build(self, knowledge: EngineeringKnowledge) -> MechanicalPlan:
        plan = MechanicalPlan()

        self._build_external_bounding_box(
            plan=plan,
            knowledge=knowledge,
        )

        self._build_component_supports(
            plan=plan,
            knowledge=knowledge,
        )

        self._build_openings(
            plan=plan,
            knowledge=knowledge,
        )

        self._build_mount_features(
            plan=plan,
            knowledge=knowledge,
        )

        self._build_validation_rules(
            plan=plan,
            knowledge=knowledge,
        )

        plan.decisions.append(
            MechanicalDecision(
                category="enclosure",
                description=(
                    "Diseñar una carcasa parametrizada a partir del "
                    "conocimiento de ingeniería."
                ),
            )
        )

        plan.manufacturing_notes.extend(
            knowledge.manufacturing.supported_processes
        )

        plan.overall_confidence = knowledge.overall_confidence

        return plan

    @staticmethod
    def _build_external_bounding_box(
        plan: MechanicalPlan,
        knowledge: EngineeringKnowledge,
    ) -> None:
        """
        Construye la envolvente exterior inicial.

        Cuando existe un componente interno, las dimensiones describen el
        objeto alojado y se añade un margen total de 4 mm. Cuando no existe
        ningún componente, las dimensiones describen la propia pieza pedida
        por el usuario y se respetan como cotas exteriores exactas.
        """

        width = knowledge.dimensions.width_mm
        depth = knowledge.dimensions.depth_mm
        height = knowledge.dimensions.height_mm

        if width and depth and height:
            enclosure_margin_mm = (
                4.0
                if knowledge.components
                else 0.0
            )

            plan.external_bounding_box = BoundingBox(
                width_mm=width + enclosure_margin_mm,
                depth_mm=depth + enclosure_margin_mm,
                height_mm=height + enclosure_margin_mm,
            )

    def _build_component_supports(
        self,
        plan: MechanicalPlan,
        knowledge: EngineeringKnowledge,
    ) -> None:
        """
        Genera los soportes mecánicos de los componentes internos.
        """

        pcb_standoff_quantity = self._find_pcb_standoff_quantity(
            knowledge
        )

        for component in knowledge.components:
            plan.internal_components.append(component.id)

            component_type = self._normalize_text(
                component.type
            )

            if self._is_pcb_component(
                component_type=component_type,
                component_name=component.name,
            ):
                mounting_point_quantity = len(
                    component.mounting_points
                )

                support_quantity = pcb_standoff_quantity

                if mounting_point_quantity > 0:
                    support_quantity = max(
                        support_quantity,
                        mounting_point_quantity,
                    )

                plan.supports.append(
                    Support(
                        target=component.id,
                        kind="pcb_standoff",
                        quantity=max(1, support_quantity),
                    )
                )

            elif self._is_battery_component(
                component_type=component_type,
                component_name=component.name,
            ):
                plan.supports.append(
                    Support(
                        target=component.id,
                        kind="battery_holder",
                        quantity=1,
                    )
                )

            elif self._is_display_component(
                component_type=component_type,
                component_name=component.name,
            ):
                plan.supports.append(
                    Support(
                        target=component.id,
                        kind="display_frame",
                        quantity=1,
                    )
                )

            else:
                plan.supports.append(
                    Support(
                        target=component.id,
                        kind="generic_support",
                        quantity=1,
                    )
                )

            plan.clearances.append(
                Clearance(
                    target=component.id,
                    value_mm=0.5,
                    reason="Montaje",
                )
            )

    @staticmethod
    def _build_openings(
        plan: MechanicalPlan,
        knowledge: EngineeringKnowledge,
    ) -> None:
        """
        Convierte puertos y botones en aperturas del plan mecánico.
        """

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

    def _build_mount_features(
        self,
        plan: MechanicalPlan,
        knowledge: EngineeringKnowledge,
    ) -> None:
        """
        Convierte los elementos de fijación en operaciones mecánicas.

        Los separadores de PCB no se añaden a mount_features porque
        ya son generados como soportes por SupportBuilder. De este modo
        se evita crear dos veces los mismos postes.
        """

        for fastener in knowledge.fasteners:
            fastener_type = self._normalize_text(
                fastener.type
            )

            if self._is_pcb_standoff_fastener(fastener_type):
                continue

            plan.mount_features.append(
                MountFeature(
                    target=fastener.type,
                    kind=self._mount_kind_from_fastener(
                        fastener_type
                    ),
                    quantity=max(1, fastener.quantity),
                )
            )

    @staticmethod
    def _build_validation_rules(
        plan: MechanicalPlan,
        knowledge: EngineeringKnowledge,
    ) -> None:
        """
        Copia las restricciones de ingeniería como reglas de validación.
        """

        for constraint in knowledge.constraints:
            plan.validation_rules.append(
                constraint.description
            )

    def _find_pcb_standoff_quantity(
        self,
        knowledge: EngineeringKnowledge,
    ) -> int:
        """
        Obtiene la cantidad de separadores de PCB definida en
        EngineeringKnowledge.

        Si no existe una cantidad explícita, utiliza cuatro soportes
        como configuración mecánica predeterminada para una PCB.
        """

        for fastener in knowledge.fasteners:
            fastener_type = self._normalize_text(
                fastener.type
            )

            if self._is_pcb_standoff_fastener(
                fastener_type
            ):
                return max(1, fastener.quantity)

        return 4

    @staticmethod
    def _is_pcb_standoff_fastener(
        fastener_type: str,
    ) -> bool:
        """
        Detecta elementos de fijación que representan separadores
        estructurales de PCB.
        """

        normalized = fastener_type.replace("_", " ")

        pcb_present = (
            "pcb" in normalized
            or "placa" in normalized
        )

        standoff_present = any(
            term in normalized
            for term in (
                "standoff",
                "separador",
                "soporte",
                "espaciador",
            )
        )

        return pcb_present and standoff_present

    @staticmethod
    def _mount_kind_from_fastener(
        fastener_type: str,
    ) -> str:
        """
        Traduce un tipo de fijación del conocimiento de ingeniería
        a un tipo admitido por FasteningBuilder.
        """

        normalized = fastener_type.replace("_", " ")

        if any(
            term in normalized
            for term in (
                "heat insert",
                "threaded insert",
                "insert",
                "inserto",
            )
        ):
            return "heat_insert"

        if any(
            term in normalized
            for term in (
                "magnet",
                "iman",
            )
        ):
            return "magnet"

        if any(
            term in normalized
            for term in (
                "snap fit",
                "snapfit",
                "clip",
                "pestana",
            )
        ):
            return "snap_fit"

        if any(
            term in normalized
            for term in (
                "adhesive",
                "adhesivo",
                "pegamento",
            )
        ):
            return "adhesive"

        return "screw"

    def _is_pcb_component(
        self,
        component_type: str,
        component_name: str,
    ) -> bool:
        """
        Detecta placas PCB aunque el agente utilice expresiones como
        'pcb', 'placa electrónica' o 'placa de circuito'.
        """

        normalized_name = self._normalize_text(
            component_name
        )

        pcb_terms = (
            "pcb",
            "placa electronica",
            "placa de circuito",
            "placa circuito",
            "circuit board",
            "printed circuit board",
        )

        return any(
            term in component_type
            or term in normalized_name
            for term in pcb_terms
        )

    def _is_battery_component(
        self,
        component_type: str,
        component_name: str,
    ) -> bool:
        """
        Detecta baterías usando el tipo y el nombre del componente.
        """

        normalized_name = self._normalize_text(
            component_name
        )

        battery_terms = (
            "battery",
            "bateria",
            "pila",
            "accumulator",
            "acumulador",
        )

        return any(
            term in component_type
            or term in normalized_name
            for term in battery_terms
        )

    def _is_display_component(
        self,
        component_type: str,
        component_name: str,
    ) -> bool:
        """
        Detecta pantallas usando el tipo y el nombre del componente.
        """

        normalized_name = self._normalize_text(
            component_name
        )

        display_terms = (
            "display",
            "screen",
            "pantalla",
            "monitor",
            "lcd",
            "oled",
            "amoled",
            "epaper",
            "e paper",
        )

        return any(
            term in component_type
            or term in normalized_name
            for term in display_terms
        )

    @staticmethod
    def _normalize_text(value: str | None) -> str:
        """
        Normaliza texto para realizar comparaciones robustas.

        - convierte a minúsculas;
        - elimina acentos;
        - sustituye guiones y guiones bajos por espacios;
        - elimina espacios duplicados.
        """

        if not value:
            return ""

        normalized = unicodedata.normalize(
            "NFKD",
            value,
        )

        normalized = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )

        normalized = normalized.lower()
        normalized = normalized.replace("-", " ")
        normalized = normalized.replace("_", " ")
        normalized = " ".join(normalized.split())

        return normalized
