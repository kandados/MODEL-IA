from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ResearchSource(BaseModel):
    """Fuente consultada durante la investigación."""

    source_id: str = Field(
        description=(
            "Identificador único de la fuente dentro del informe, "
            "por ejemplo SRC-001"
        )
    )

    title: str = Field(
        description="Título de la página o documento"
    )

    url: str = Field(
        description="Dirección completa de la fuente"
    )

    source_type: Literal[
        "official_product_page",
        "official_documentation",
        "official_manual",
        "technical_drawing",
        "cad_model",
        "reliable_database",
        "community_source",
        "other",
    ] = Field(
        description="Tipo de fuente"
    )

    manufacturer_source: bool = Field(
        description="Indica si la fuente pertenece al fabricante"
    )


class TechnicalFact(BaseModel):
    """Dato técnico obtenido durante la investigación."""

    category: Literal[
        "dimension",
        "weight",
        "geometry",
        "port",
        "button",
        "ventilation",
        "mounting",
        "clearance",
        "material",
        "cad_resource",
        "other",
    ] = Field(
        description="Categoría del dato técnico"
    )

    name: str = Field(
        description="Nombre preciso del dato"
    )

    value: str = Field(
        description=(
            "Valor encontrado, incluyendo unidades cuando corresponda"
        )
    )

    evidence: str = Field(
        description=(
            "Fragmento, dato concreto o explicación breve que respalda "
            "la información encontrada"
        )
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confianza entre 0 y 1"
    )

    source_ids: list[str] = Field(
        description=(
            "Identificadores de las fuentes que respaldan el dato, "
            "por ejemplo SRC-001"
        )
    )


class ObjectResearch(BaseModel):
    """Investigación de un objeto físico concreto."""

    object_name: str = Field(
        description="Nombre del objeto investigado"
    )

    manufacturer: str | None = Field(
        description="Fabricante identificado o null"
    )

    model: str | None = Field(
        description="Modelo exacto identificado o null"
    )

    identity_confirmed: bool = Field(
        description="Indica si se confirmó inequívocamente el producto"
    )

    identity_notes: str = Field(
        description="Aclaraciones sobre la identificación"
    )

    technical_facts: list[TechnicalFact] = Field(
        description="Datos técnicos encontrados"
    )

    sources: list[ResearchSource] = Field(
        description="Fuentes consultadas"
    )

    unresolved_information: list[str] = Field(
        description="Información que no pudo encontrarse con fiabilidad"
    )

    contradictions: list[str] = Field(
        description="Contradicciones detectadas entre fuentes"
    )

    overall_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confianza global de la investigación"
    )

    @model_validator(mode="after")
    def validate_source_references(self) -> ObjectResearch:
        """
        Comprueba que los identificadores de fuente sean únicos y que todos
        los datos técnicos apunten a fuentes existentes en el informe.
        """

        available_source_ids = [
            source.source_id
            for source in self.sources
        ]

        unique_source_ids = set(available_source_ids)

        if len(available_source_ids) != len(unique_source_ids):
            raise ValueError(
                "Los source_id de las fuentes deben ser únicos "
                "dentro de cada objeto investigado."
            )

        for technical_fact in self.technical_facts:
            unknown_source_ids = [
                source_id
                for source_id in technical_fact.source_ids
                if source_id not in unique_source_ids
            ]

            if unknown_source_ids:
                unknown_ids_text = ", ".join(unknown_source_ids)

                raise ValueError(
                    f'El dato técnico "{technical_fact.name}" referencia '
                    f"fuentes inexistentes: {unknown_ids_text}."
                )

        return self


class ResearchReport(BaseModel):
    """Resultado completo de la investigación web."""

    original_request: str = Field(
        description="Petición original del usuario"
    )

    researched_at: str = Field(
        description=(
            "Fecha y hora de la investigación en formato ISO 8601"
        )
    )

    researched_objects: list[ObjectResearch] = Field(
        description="Objetos investigados"
    )

    research_complete: bool = Field(
        description="Indica si se encontró información suficiente"
    )

    missing_critical_information: list[str] = Field(
        description="Información crítica que sigue faltando"
    )

    report_summary: str = Field(
        description="Resumen preciso de los resultados"
    )