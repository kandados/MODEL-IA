from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from src.agent.design_agent import DesignAgent
from src.cad.cad_generator import CADGenerationResult, CADGenerator
from src.knowledge.knowledge_builder import KnowledgeBuilder
from src.models.design_request import DesignRequest
from src.models.engineering_knowledge import EngineeringKnowledge
from src.models.mechanical_plan import MechanicalPlan
from src.models.research_report import ResearchReport
from src.planner.mechanical_planner import MechanicalPlanner
from src.research.web_researcher import WebResearcher


ProgressCallback = Callable[["GenerationProgress"], None]


@dataclass(frozen=True, slots=True)
class GenerationProgress:
    stage: str
    stage_index: int
    progress: float
    message: str


@dataclass(slots=True)
class GenerationPipelineResult:
    design_request: DesignRequest
    research_report: ResearchReport | None
    engineering_knowledge: EngineeringKnowledge
    mechanical_plan: MechanicalPlan
    cad_result: CADGenerationResult
    file_name: str
    formats: tuple[str, ...]


def safe_file_name(value: str) -> str:
    """Convierte un nombre descriptivo en un nombre de archivo seguro."""

    normalized = re.sub(
        r"[^a-zA-Z0-9_-]+",
        "_",
        value.strip(),
    )
    normalized = normalized.strip("_").lower()

    return normalized or "model_ia_generated"


def normalize_formats(
    requested_output: Iterable[str],
) -> tuple[str, ...]:
    """Normaliza, filtra y deduplica los formatos CAD solicitados."""

    supported = {
        "step",
        "stl",
        "3mf",
    }
    formats: list[str] = []

    for item in requested_output:
        normalized = item.strip().lower().lstrip(".")

        if normalized in supported and normalized not in formats:
            formats.append(normalized)

    return tuple(formats or ("step", "stl", "3mf"))


def determine_file_name(
    design_request: DesignRequest,
) -> str:
    """Determina un nombre representativo para los archivos generados."""

    intent_names = {
        "enclosure": "enclosure",
        "protective_case": "protective_case",
        "support": "support",
        "mount": "mount",
        "adapter": "adapter",
        "replacement_part": "replacement_part",
        "container": "container",
        "mechanical_part": "mechanical_part",
        "unknown": "model_ia_generated",
    }

    return safe_file_name(
        intent_names.get(
            design_request.design_intent,
            "model_ia_generated",
        )
    )


def determine_material(
    design_request: DesignRequest,
) -> str:
    """Extrae el material de fabricación mencionado expresamente."""

    searchable_text = " ".join(
        [
            design_request.original_request,
            *design_request.explicit_requirements,
        ]
    ).lower()

    material_patterns = (
        (r"\bpa[\s-]?cf\b", "PA-CF"),
        (r"\bpla[\s-]?cf\b", "PLA-CF"),
        (r"\bpetg\b", "PETG"),
        (r"\bpla\b", "PLA"),
        (r"\babs\b", "ABS"),
        (r"\basa\b", "ASA"),
        (r"\btpu\b", "TPU"),
        (r"\bnylon\b", "Nylon"),
    )

    for pattern, material in material_patterns:
        if re.search(pattern, searchable_text, flags=re.IGNORECASE):
            return material

    return "Sin definir"


def determine_tolerance_mm(
    design_request: DesignRequest,
    default_value: float = 0.5,
) -> float:
    """Extrae una tolerancia u holgura explícita, si está disponible."""

    searchable_text = " ".join(
        [
            design_request.original_request,
            *design_request.explicit_requirements,
        ]
    )
    match = re.search(
        r"(?:tolerancia|holgura|tolerance|clearance)"
        r"\s*(?:de|=|:)?\s*"
        r"([0-9]+(?:[.,][0-9]+)?)\s*mm\b",
        searchable_text,
        flags=re.IGNORECASE,
    )

    if match is None:
        return default_value

    return float(match.group(1).replace(",", "."))


class GenerationPipeline:
    """
    Orquesta el pipeline completo sin depender de consola, HTTP o Electron.

    Esta clase es la única entrada de alto nivel para generar un diseño. Tanto
    la CLI como FastAPI la utilizan para evitar dos implementaciones distintas
    del mismo proceso.
    """

    def __init__(
        self,
        *,
        design_agent: DesignAgent | None = None,
        web_researcher: WebResearcher | None = None,
        knowledge_builder: KnowledgeBuilder | None = None,
        mechanical_planner: MechanicalPlanner | None = None,
        cad_generator: CADGenerator | None = None,
    ) -> None:
        self.design_agent = design_agent
        self.web_researcher = web_researcher
        self.knowledge_builder = knowledge_builder or KnowledgeBuilder()
        self.mechanical_planner = mechanical_planner or MechanicalPlanner()
        self.cad_generator = cad_generator or CADGenerator()

    def run(
        self,
        user_request: str,
        *,
        requested_formats: Iterable[str] | None = None,
        output_directory: str | Path = "projects/generated",
        on_progress: ProgressCallback | None = None,
    ) -> GenerationPipelineResult:
        request = user_request.strip()

        if not request:
            raise ValueError("La petición no puede estar vacía.")

        self._emit(
            on_progress,
            stage="interpret",
            stage_index=0,
            progress=0.05,
            message="Interpretando la petición",
        )

        design_agent = self.design_agent or DesignAgent()
        design_request = design_agent.interpret(request)

        research_report: ResearchReport | None = None

        if design_request.web_research_required:
            self._emit(
                on_progress,
                stage="research",
                stage_index=0,
                progress=0.20,
                message="Investigando datos técnicos necesarios",
            )
            researcher = self.web_researcher or WebResearcher()
            research_report = researcher.research(design_request)

        self._emit(
            on_progress,
            stage="knowledge",
            stage_index=1,
            progress=0.35,
            message="Consolidando el conocimiento de ingeniería",
        )
        engineering_knowledge = self.knowledge_builder.build(
            design_request=design_request,
            report=research_report,
        )

        self._emit(
            on_progress,
            stage="plan",
            stage_index=1,
            progress=0.50,
            message="Construyendo el plan mecánico",
        )
        mechanical_plan = self.mechanical_planner.build(
            engineering_knowledge
        )

        if mechanical_plan.external_bounding_box is None:
            raise ValueError(
                "La petición no contiene dimensiones suficientes para "
                "generar geometría CAD."
            )

        formats = normalize_formats(
            requested_formats or design_request.requested_output
        )
        file_name = determine_file_name(design_request)

        self._emit(
            on_progress,
            stage="cad",
            stage_index=1,
            progress=0.65,
            message="Generando la geometría paramétrica",
        )
        self._emit(
            on_progress,
            stage="validate",
            stage_index=2,
            progress=0.78,
            message="Validando la geometría CAD",
        )

        cad_result = self.cad_generator.generate_and_export(
            mechanical_plan,
            file_name=file_name,
            formats=formats,
            output_directory=output_directory,
        )

        self._emit(
            on_progress,
            stage="export",
            stage_index=3,
            progress=1.0,
            message="Archivos de fabricación preparados",
        )

        return GenerationPipelineResult(
            design_request=design_request,
            research_report=research_report,
            engineering_knowledge=engineering_knowledge,
            mechanical_plan=mechanical_plan,
            cad_result=cad_result,
            file_name=file_name,
            formats=formats,
        )

    @staticmethod
    def _emit(
        callback: ProgressCallback | None,
        *,
        stage: str,
        stage_index: int,
        progress: float,
        message: str,
    ) -> None:
        if callback is None:
            return

        callback(
            GenerationProgress(
                stage=stage,
                stage_index=stage_index,
                progress=progress,
                message=message,
            )
        )
