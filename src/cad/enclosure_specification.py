from __future__ import annotations

import re
from dataclasses import dataclass

from src.models.mechanical_plan import BoundingBox, MechanicalPlan


@dataclass(frozen=True)
class EnclosureSpecification:
    """
    Especificación geométrica resuelta de una carcasa.

    Esta clase constituye la única fuente de verdad para los parámetros
    geométricos compartidos por:

    - EnclosureBuilder;
    - GeometricReferenceSystem;
    - futuros validadores;
    - futuros planificadores de colocación.
    """

    external_box: BoundingBox

    wall_thickness_mm: float
    corner_radius_mm: float
    base_height_ratio: float

    @property
    def base_height_mm(self) -> float:
        return (
            self.external_box.height_mm
            * self.base_height_ratio
        )

    @property
    def lid_height_mm(self) -> float:
        return (
            self.external_box.height_mm
            - self.base_height_mm
        )

    @classmethod
    def from_plan(
        cls,
        plan: MechanicalPlan,
        *,
        default_wall_thickness_mm: float = 2.0,
        default_corner_radius_mm: float = 2.0,
        default_base_height_ratio: float = 0.60,
    ) -> EnclosureSpecification:
        """
        Construye la especificación a partir del MechanicalPlan.

        Durante esta fase mantiene compatibilidad con las reglas textuales
        existentes en validation_rules.
        """

        external_box = cls._require_external_box(plan)

        wall_thickness = cls._resolve_numeric_rule(
            rules=plan.validation_rules,
            patterns=(
                r"wall_thickness\s*=\s*([0-9]+(?:[.,][0-9]+)?)",
                r"wall thickness\s*=\s*([0-9]+(?:[.,][0-9]+)?)",
                r"grosor(?:\s+de)?\s+pared(?:es)?\s*=\s*"
                r"([0-9]+(?:[.,][0-9]+)?)",
            ),
            default_value=default_wall_thickness_mm,
        )

        corner_radius = cls._resolve_numeric_rule(
            rules=plan.validation_rules,
            patterns=(
                r"corner_radius\s*=\s*([0-9]+(?:[.,][0-9]+)?)",
                r"corner radius\s*=\s*([0-9]+(?:[.,][0-9]+)?)",
                r"radio(?:\s+de)?\s+esquina(?:s)?\s*=\s*"
                r"([0-9]+(?:[.,][0-9]+)?)",
            ),
            default_value=default_corner_radius_mm,
        )

        base_height_ratio = cls._resolve_numeric_rule(
            rules=plan.validation_rules,
            patterns=(
                r"base_height_ratio\s*=\s*"
                r"([0-9]+(?:[.,][0-9]+)?)",
                r"base height ratio\s*=\s*"
                r"([0-9]+(?:[.,][0-9]+)?)",
                r"proporci[oó]n(?:\s+de)?\s+base\s*=\s*"
                r"([0-9]+(?:[.,][0-9]+)?)",
            ),
            default_value=default_base_height_ratio,
        )

        specification = cls(
            external_box=external_box,
            wall_thickness_mm=wall_thickness,
            corner_radius_mm=corner_radius,
            base_height_ratio=base_height_ratio,
        )

        specification.validate()

        return specification

    def validate(self) -> None:
        """Valida la coherencia geométrica de la especificación."""

        dimensions = {
            "width_mm": self.external_box.width_mm,
            "depth_mm": self.external_box.depth_mm,
            "height_mm": self.external_box.height_mm,
            "wall_thickness_mm": self.wall_thickness_mm,
        }

        for name, value in dimensions.items():
            if value <= 0:
                raise ValueError(
                    f"{name} debe ser mayor que cero. "
                    f"Valor recibido: {value}"
                )

        if self.corner_radius_mm < 0:
            raise ValueError(
                "El radio de esquina no puede ser negativo."
            )

        if not 0.0 < self.base_height_ratio < 1.0:
            raise ValueError(
                "La proporción de altura de la base debe estar "
                "comprendida entre 0 y 1."
            )

        minimum_horizontal_dimension = (
            self.wall_thickness_mm
            * 2.0
        )

        if self.external_box.width_mm <= minimum_horizontal_dimension:
            raise ValueError(
                "El ancho exterior no permite aplicar el grosor "
                "de pared solicitado."
            )

        if self.external_box.depth_mm <= minimum_horizontal_dimension:
            raise ValueError(
                "La profundidad exterior no permite aplicar el grosor "
                "de pared solicitado."
            )

        if self.base_height_mm <= self.wall_thickness_mm:
            raise ValueError(
                "La altura de la base no permite crear suelo y cavidad."
            )

        if self.lid_height_mm <= self.wall_thickness_mm:
            raise ValueError(
                "La altura de la tapa no permite crear techo y cavidad."
            )

    @staticmethod
    def _require_external_box(
        plan: MechanicalPlan,
    ) -> BoundingBox:
        box = plan.external_bounding_box

        if box is None:
            raise ValueError(
                "MechanicalPlan no contiene dimensiones exteriores."
            )

        return box

    @staticmethod
    def _resolve_numeric_rule(
        *,
        rules: list[str],
        patterns: tuple[str, ...],
        default_value: float,
    ) -> float:
        for rule in rules:
            normalized = rule.strip().lower()

            for pattern in patterns:
                match = re.search(
                    pattern,
                    normalized,
                )

                if match is None:
                    continue

                value_text = (
                    match
                    .group(1)
                    .replace(",", ".")
                )

                try:
                    value = float(value_text)
                except ValueError:
                    continue

                return value

        return default_value