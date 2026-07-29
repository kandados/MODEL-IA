from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Dimension(BaseModel):
    """Dimensión indicada expresamente por el usuario."""

    name: str = Field(
        description="Nombre de la dimensión: ancho, alto, largo, diámetro, etc."
    )

    value_mm: float = Field(
        description="Valor convertido a milímetros"
    )


class IdentifiedObject(BaseModel):
    """Objeto físico real mencionado en la petición."""

    name: str = Field(
        description="Nombre concreto del objeto físico o producto"
    )

    manufacturer: str | None = Field(
        description="Fabricante identificado o null"
    )

    model: str | None = Field(
        description="Modelo exacto identificado o null"
    )

    object_type: str = Field(
        description="Tipo general del objeto"
    )

    role: Literal[
        "design_subject",
        "installation_context",
        "reference_object",
    ] = Field(
        description=(
            "design_subject: objeto para el que se diseña; "
            "installation_context: objeto donde se instalará; "
            "reference_object: objeto usado como referencia"
        )
    )

    requires_web_research: bool = Field(
        description="Indica si deben investigarse datos técnicos del objeto"
    )


class DesignRequest(BaseModel):
    """Interpretación estructurada de una petición de diseño."""

    original_request: str = Field(
        description="Petición original completa del usuario"
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
        description="Intención mecánica principal"
    )

    requested_output: list[
        Literal["STEP", "STL", "3MF"]
    ] = Field(
        description=(
            "Formatos solicitados. Si el usuario no especifica ninguno, "
            "debe contener STEP, STL y 3MF"
        )
    )

    identified_objects: list[IdentifiedObject] = Field(
        description="Objetos físicos reales mencionados"
    )

    explicit_dimensions: list[Dimension] = Field(
        description="Dimensiones indicadas expresamente por el usuario"
    )

    explicit_requirements: list[str] = Field(
        description="Requisitos expresamente indicados"
    )

    web_research_required: bool = Field(
        description="Indica si la petición requiere investigación web"
    )

    information_to_research: list[str] = Field(
        description="Información técnica objetiva que debe investigarse"
    )

    missing_user_decisions: list[str] = Field(
        description=(
            "Solo decisiones subjetivas imprescindibles que no puedan "
            "investigarse ni resolverse mediante criterio de ingeniería"
        )
    )

    interpretation_summary: str = Field(
        description="Resumen preciso de la interpretación"
    )

    @model_validator(mode="after")
    def ensure_default_outputs(self) -> "DesignRequest":
        if not self.requested_output:
            self.requested_output = ["STEP", "STL", "3MF"]

        return self