from __future__ import annotations

import json
import re
import traceback
from pathlib import Path

from src.agent.design_agent import DesignAgent, DesignAgentError
from src.cad.cad_generator import CADGenerator
from src.cad.validation import CADValidationError
from src.knowledge.knowledge_builder import KnowledgeBuilder
from src.models.research_report import ResearchReport
from src.planner.mechanical_planner import MechanicalPlanner
from src.research.web_researcher import WebResearchError, WebResearcher


OUTPUT_DIRECTORY = Path("projects/generated")


def print_json(data: object) -> None:
    """Imprime datos serializables en formato JSON legible."""

    print(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
    )


def print_exception(
    stage: str,
    exc: Exception,
) -> None:
    """
    Muestra información completa de una excepción.

    Algunas excepciones procedentes de CadQuery u OpenCascade no contienen
    mensaje de texto. Por eso se imprime también el tipo, la representación
    interna y el traceback completo.
    """

    print(f"\nERROR EN {stage}")
    print(f"Tipo: {type(exc).__name__}")
    print(f"Mensaje: {str(exc) or '<sin mensaje>'}")
    print(f"Representación: {exc!r}")
    print("\nTRACEBACK COMPLETO:")
    traceback.print_exc()


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
    requested_output: list[str],
) -> tuple[str, ...]:
    """Normaliza y filtra los formatos CAD solicitados."""

    supported = {
        "step",
        "stl",
        "3mf",
    }

    formats: list[str] = []

    for item in requested_output:
        normalized = item.strip().lower().lstrip(".")

        if (
            normalized in supported
            and normalized not in formats
        ):
            formats.append(normalized)

    return tuple(
        formats
        or (
            "step",
            "stl",
            "3mf",
        )
    )


def run_research_if_required(
    design_request,
) -> ResearchReport | None:
    """
    Ejecuta investigación web únicamente cuando DesignRequest lo requiere.

    Las peticiones geométricas autosuficientes continúan directamente sin
    crear un ResearchReport artificial.
    """

    if not design_request.web_research_required:
        print(
            "\nINVESTIGACIÓN WEB\n"
            "No necesaria. La petición contiene información suficiente."
        )
        return None

    research_report = WebResearcher().research(
        design_request
    )

    print("\nRESEARCH REPORT\n")
    print_json(
        research_report.model_dump()
    )

    return research_report


def determine_file_name(
    design_request,
) -> str:
    """
    Determina un nombre representativo para los archivos generados.

    El nombre se basa prioritariamente en la intención de diseño.

    Los elementos de identified_objects representan componentes,
    dispositivos u objetos relacionados con la pieza, pero no
    necesariamente la pieza que se está diseñando. Por ejemplo, en una
    caja para una placa PCB, la PCB es un componente interno y la pieza
    generada sigue siendo una carcasa.
    """

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

    design_intent = getattr(
        design_request,
        "design_intent",
        "unknown",
    )

    file_name = intent_names.get(
        design_intent,
        "model_ia_generated",
    )

    return safe_file_name(file_name)


def main() -> None:
    print("=" * 60)
    print("MODEL-IA")
    print("Pipeline completo: petición -> investigación -> CAD")
    print("=" * 60)

    user_request = input(
        "\nDescribe la pieza que necesitas:\n> "
    ).strip()

    if not user_request:
        print(
            "\nERROR: Debes describir la pieza que necesitas."
        )
        return

    try:
        design_request = DesignAgent().interpret(
            user_request
        )
    except DesignAgentError as exc:
        print(
            f"\nERROR DE INTERPRETACIÓN: {exc}"
        )
        return
    except Exception as exc:
        print_exception(
            "LA INTERPRETACIÓN DE LA PETICIÓN",
            exc,
        )
        return

    print("\nDESIGN REQUEST\n")
    print_json(
        design_request.model_dump()
    )

    try:
        research_report = run_research_if_required(
            design_request
        )
    except WebResearchError as exc:
        print(
            f"\nERROR DE INVESTIGACIÓN: {exc}"
        )
        return
    except Exception as exc:
        print_exception(
            "LA INVESTIGACIÓN WEB",
            exc,
        )
        return

    try:
        engineering_knowledge = KnowledgeBuilder().build(
            design_request=design_request,
            report=research_report,
        )
    except Exception as exc:
        print_exception(
            "LA GENERACIÓN DE ENGINEERING KNOWLEDGE",
            exc,
        )
        return

    print("\nENGINEERING KNOWLEDGE\n")
    print_json(
        engineering_knowledge.model_dump()
    )

    try:
        mechanical_plan = MechanicalPlanner().build(
            engineering_knowledge
        )
    except Exception as exc:
        print_exception(
            "LA GENERACIÓN DEL MECHANICAL PLAN",
            exc,
        )
        return

    print("\nMECHANICAL PLAN\n")
    print_json(
        mechanical_plan.model_dump()
    )

    if mechanical_plan.external_bounding_box is None:
        print(
            "\nERROR CAD: El plan no contiene dimensiones exteriores "
            "suficientes para generar geometría."
        )
        return

    file_name = determine_file_name(
        design_request
    )

    formats = normalize_formats(
        design_request.requested_output
    )

    print("\nGENERACIÓN CAD")
    print(f"Nombre base: {file_name}")
    print(
        "Formatos: "
        f"{', '.join(format_.upper() for format_ in formats)}"
    )
    print(f"Directorio: {OUTPUT_DIRECTORY}")

    try:
        cad_result = CADGenerator().generate_and_export(
            mechanical_plan,
            file_name=file_name,
            formats=formats,
            output_directory=OUTPUT_DIRECTORY,
        )
    except CADValidationError as exc:
        print("\nERROR DE VALIDACIÓN CAD")

        if exc.result.errors:
            for issue in exc.result.errors:
                print(
                    f"- [{issue.code}] {issue.message}"
                )
        else:
            print(
                "- La validación falló, pero no devolvió "
                "errores descriptivos."
            )

        print(f"\nRepresentación: {exc!r}")
        print("\nTRACEBACK COMPLETO:")
        traceback.print_exc()
        return
    except Exception as exc:
        print_exception(
            "LA GENERACIÓN O EXPORTACIÓN CAD",
            exc,
        )
        return

    print("\nVALIDACIÓN CAD")
    print(
        "Estado: "
        f"{'OK' if cad_result.validation.is_valid else 'ERROR'}"
    )

    for issue in cad_result.validation.warnings:
        print(
            f"ADVERTENCIA [{issue.code}]: "
            f"{issue.message}"
        )

    print("\nARCHIVOS GENERADOS")

    if cad_result.exports:
        for part_name, export_result in cad_result.exports.items():
            print(
                f"\n{part_name.upper()}:"
            )

            if export_result.files:
                for exported_file in export_result.files:
                    print(
                        f"- {exported_file.format.upper()}: "
                        f"{exported_file.path}"
                    )
            else:
                print(
                    "- No se generaron archivos para esta pieza."
                )
    else:
        print(
            "No se exportó ningún archivo."
        )

    print(
        "\nPipeline completado correctamente."
    )


if __name__ == "__main__":
    main()