from __future__ import annotations

import json
import traceback
from pathlib import Path

from src.agent.design_agent import DesignAgentError
from src.cad.validation import CADValidationError
from src.generation_service import (
    GenerationPipeline,
    GenerationProgress,
)
from src.research.web_researcher import WebResearchError


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
    """Muestra información completa de una excepción inesperada."""

    print(f"\nERROR EN {stage}")
    print(f"Tipo: {type(exc).__name__}")
    print(f"Mensaje: {str(exc) or '<sin mensaje>'}")
    print(f"Representación: {exc!r}")
    print("\nTRACEBACK COMPLETO:")
    traceback.print_exc()


def print_progress(progress: GenerationProgress) -> None:
    """Muestra el avance emitido por el pipeline compartido."""

    percentage = round(progress.progress * 100)
    print(
        f"\n[{progress.stage.upper()} · {percentage}%] "
        f"{progress.message}"
    )


def main() -> None:
    print("=" * 60)
    print("MODEL-IA")
    print("Pipeline completo: petición -> investigación -> CAD")
    print("=" * 60)

    user_request = input(
        "\nDescribe la pieza que necesitas:\n> "
    ).strip()

    if not user_request:
        print("\nERROR: Debes describir la pieza que necesitas.")
        return

    try:
        result = GenerationPipeline().run(
            user_request,
            output_directory=OUTPUT_DIRECTORY,
            on_progress=print_progress,
        )
    except DesignAgentError as exc:
        print(f"\nERROR DE INTERPRETACIÓN: {exc}")
        return
    except WebResearchError as exc:
        print(f"\nERROR DE INVESTIGACIÓN: {exc}")
        return
    except CADValidationError as exc:
        print("\nERROR DE VALIDACIÓN CAD")

        if exc.result.errors:
            for issue in exc.result.errors:
                print(f"- [{issue.code}] {issue.message}")
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
        print_exception("EL PIPELINE DE GENERACIÓN", exc)
        return

    print("\nDESIGN REQUEST\n")
    print_json(result.design_request.model_dump())

    if result.research_report is None:
        print(
            "\nINVESTIGACIÓN WEB\n"
            "No necesaria. La petición contiene información suficiente."
        )
    else:
        print("\nRESEARCH REPORT\n")
        print_json(result.research_report.model_dump())

    print("\nENGINEERING KNOWLEDGE\n")
    print_json(result.engineering_knowledge.model_dump())

    print("\nMECHANICAL PLAN\n")
    print_json(result.mechanical_plan.model_dump())

    print("\nGENERACIÓN CAD")
    print(f"Nombre base: {result.file_name}")
    print(
        "Formatos: "
        f"{', '.join(format_.upper() for format_ in result.formats)}"
    )
    print(f"Directorio: {OUTPUT_DIRECTORY}")

    print("\nVALIDACIÓN CAD")
    print(
        "Estado: "
        f"{'OK' if result.cad_result.validation.is_valid else 'ERROR'}"
    )

    for issue in result.cad_result.validation.warnings:
        print(f"ADVERTENCIA [{issue.code}]: {issue.message}")

    print("\nARCHIVOS GENERADOS")

    if result.cad_result.exports:
        for part_name, export_result in result.cad_result.exports.items():
            print(f"\n{part_name.upper()}:")

            if export_result.files:
                for exported_file in export_result.files:
                    print(
                        f"- {exported_file.format.upper()}: "
                        f"{exported_file.path}"
                    )
            else:
                print("- No se generaron archivos para esta pieza.")
    else:
        print("No se exportó ningún archivo.")

    print("\nPipeline completado correctamente.")


if __name__ == "__main__":
    main()
