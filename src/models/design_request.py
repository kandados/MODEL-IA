from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IdentifiedObject(BaseModel):
    """Objeto físico o producto detectado en la petición."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description="Nombre común del objeto o producto.",
    )

    manufacturer: str | None = Field(
        description=(
            "Fabricante indicado o identificado. Debe ser null cuando "
            "no se conozca."
        ),
    )

    model: str | None = Field(
        description=(
            "Modelo exacto indicado o identificado. Debe ser null cuando "
            "no se conozca."
        ),
    )

    object_type: str = Field(
        description=(
            "Tipo general del objeto: ordenador, mando, pantalla, caja, "
            "placa, soporte, pieza mecánica, etc."
        ),
    )

    requires_web_research: bool = Field(
        description=(
            "Indica si es necesario investigar datos técnicos del objeto "
            "en Internet."
        ),
    )


class ExplicitDimension(BaseModel):
    """Dimensión explícita indicada por el usuario."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        description=(
            "Nombre normalizado de la dimensión, por ejemplo width, depth, "
            "height, diameter o wall_thickness."
        ),
    )

    value_mm: float = Field(
        gt=0,
        description="Valor de la dimensión expresado en milímetros.",
    )


class DesignRequest(BaseModel):
    """Interpretación estructurada de la petición del usuario."""

    model_config = ConfigDict(extra="forbid")

    original_request: str = Field(
        description="Petición original completa del usuario.",
    )

    design_intent: Literal[
        "enclosure",
        "protective_case",
        "support",
        "mount",
        "adapter",
        "replacement_part",
        "container",
        "mechanical_part",
        "unknown",
    ] = Field(
        description="Intención mecánica principal de la petición.",
    )

    requested_output: list[
        Literal["STEP", "STL", "3MF"]
    ] = Field(
        description="Formatos CAD que deben generarse.",
    )

    identified_objects: list[IdentifiedObject] = Field(
        description="Objetos físicos identificados en la petición.",
    )

    explicit_dimensions_mm: list[ExplicitDimension] = Field(
        description=(
            "Dimensiones explícitas indicadas por el usuario, expresadas "
            "como una lista de nombre y valor en milímetros."
        ),
    )

    explicit_requirements: list[str] = Field(
        description=(
            "Requisitos explícitos de diseño, fabricación, montaje o uso."
        ),
    )

    web_research_required: bool = Field(
        description=(
            "Indica si hace falta investigación web antes de diseñar."
        ),
    )

    information_to_research: list[str] = Field(
        description=(
            "Información técnica concreta que debe investigarse."
        ),
    )

    missing_user_decisions: list[str] = Field(
        description=(
            "Decisiones relevantes que todavía tendría que tomar el usuario."
        ),
    )

    interpretation_summary: str = Field(
        description=(
            "Resumen técnico breve y preciso de la petición interpretada."
        ),
    )

    def dimensions_as_dict(self) -> dict[str, float]:
        """Devuelve las dimensiones como diccionario para uso interno."""

        return {
            dimension.name: dimension.value_mm
            for dimension in self.explicit_dimensions_mm
        }