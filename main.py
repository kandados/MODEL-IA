from __future__ import annotations

import json

from src.agent.design_agent import DesignAgent, DesignAgentError


def main() -> None:
    print("=" * 60)
    print("MODEL-IA")
    print("Comprensión inicial de una petición de diseño")
    print("=" * 60)

    user_request = input("\nDescribe la pieza que necesitas:\n> ").strip()

    try:
        agent = DesignAgent()
        design_request = agent.interpret(user_request)

    except DesignAgentError as exc:
        print(f"\nERROR: {exc}")
        return

    print("\nInterpretación de Model-IA:\n")

    print(
        json.dumps(
            design_request.model_dump(),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()