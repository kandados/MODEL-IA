from __future__ import annotations

import json

from src.agent.design_agent import DesignAgent, DesignAgentError
from src.research.web_researcher import (
    WebResearchError,
    WebResearcher,
)


def print_json(data: object) -> None:
    print(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    print("=" * 60)
    print("MODEL-IA")
    print("Comprensión e investigación técnica")
    print("=" * 60)

    user_request = input(
        "\nDescribe la pieza que necesitas:\n> "
    ).strip()

    try:
        agent = DesignAgent()
        design_request = agent.interpret(user_request)

    except DesignAgentError as exc:
        print(f"\nERROR DE INTERPRETACIÓN: {exc}")
        return

    print("\nInterpretación de Model-IA:\n")
    print_json(design_request.model_dump())

    if not design_request.web_research_required:
        print("\nNo se necesita investigación web.")
        return

    print("\nInvestigando información técnica en Internet...\n")

    try:
        researcher = WebResearcher()
        research_report = researcher.research(design_request)

    except WebResearchError as exc:
        print(f"\nERROR DE INVESTIGACIÓN: {exc}")
        return

    print("\nInforme técnico de Model-IA:\n")
    print_json(research_report.model_dump())


if __name__ == "__main__":
    main()