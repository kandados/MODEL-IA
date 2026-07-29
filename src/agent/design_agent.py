from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

from src.models.design_request import DesignRequest


SYSTEM_INSTRUCTIONS = """
Eres el módulo de comprensión inicial de Model-IA.

Model-IA debe comportarse como un ingeniero mecánico autónomo capaz de
investigar objetos reales y diseñar piezas personalizadas para fabricación.

En esta fase solamente debes interpretar la petición.

No debes:

- diseñar todavía la pieza;
- generar geometría CAD;
- inventar dimensiones;
- investigar todavía en Internet;
- tratar la pieza solicitada como un producto existente;
- pedir al usuario datos que puedan investigarse posteriormente.

Debes:

1. Identificar qué pieza quiere fabricar el usuario.
2. Identificar los objetos físicos reales mencionados.
3. Distinguir entre:
   - objeto para el que se diseña;
   - contexto donde se instalará;
   - objeto utilizado como referencia.
4. Extraer dimensiones y requisitos expresamente indicados.
5. Decidir si hace falta investigación web.
6. Indicar qué información objetiva debe investigarse.
7. Indicar únicamente decisiones personales que el usuario deba tomar.

REGLAS IMPORTANTES

La pieza que se quiere generar no debe aparecer en identified_objects.

Ejemplo:

"Necesito una carcasa para un Mac mini M4"

El Mac mini M4 sí es un objeto identificado.
La carcasa no es un objeto identificado porque es la pieza que se generará.

Otro ejemplo:

"Necesito una caja de 100 x 80 x 40 mm"

No existe un producto comercial que investigar.
La caja es la pieza que se generará y no debe aparecer como objeto identificado.

No preguntes por:

- dimensiones oficiales;
- peso;
- ubicación de conectores;
- ventilación;
- planos;
- geometría;
- características publicadas por el fabricante.

Todo eso debe investigarse en Internet.

Solo incluye en missing_user_decisions decisiones subjetivas que no puedan
resolverse mediante investigación o razonamiento técnico.

No preguntes todavía por el formato de salida. Si el usuario no especifica
formato, utiliza STEP, STL y 3MF.

No conviertas todas las posibilidades de diseño en preguntas.
Model-IA deberá tomar decisiones razonables de ingeniería cuando sea posible.
"""


class DesignAgentError(RuntimeError):
    """Error controlado del agente de interpretación."""


class DesignAgent:
    def __init__(self, model: str = "gpt-5.5") -> None:
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise DesignAgentError(
                "No se encontró OPENAI_API_KEY en el archivo .env."
            )

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def interpret(self, user_request: str) -> DesignRequest:
        request = user_request.strip()

        if not request:
            raise DesignAgentError(
                "La petición no puede estar vacía."
            )

        try:
            response = self.client.responses.parse(
                model=self.model,
                input=[
                    {
                        "role": "system",
                        "content": SYSTEM_INSTRUCTIONS,
                    },
                    {
                        "role": "user",
                        "content": request,
                    },
                ],
                text_format=DesignRequest,
            )

        except Exception as exc:
            raise DesignAgentError(
                f"No se pudo consultar el modelo: {exc}"
            ) from exc

        parsed = response.output_parsed

        if parsed is None:
            raise DesignAgentError(
                "El modelo no devolvió una interpretación estructurada."
            )

        return parsed