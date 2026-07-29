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
2. Identificar todos los objetos físicos reales mencionados que interactúan
   con la pieza que se va a diseñar.
3. Distinguir entre:
   - la pieza que se generará;
   - el objeto que la pieza alojará, protegerá, soportará o fijará;
   - el contexto donde se instalará;
   - el objeto utilizado como referencia.
4. Extraer dimensiones y requisitos expresamente indicados.
5. Decidir si hace falta investigación web.
6. Indicar qué información objetiva debe investigarse.
7. Indicar únicamente decisiones personales que el usuario deba tomar.

REGLAS IMPORTANTES

La pieza que se quiere generar no debe aparecer en identified_objects.

Sin embargo, cualquier objeto físico que la pieza deba alojar, proteger,
sujetar, soportar, adaptar, cubrir, fijar o rodear sí debe aparecer en
identified_objects.

Ejemplo:

"Necesito una carcasa para un Mac mini M4"

El Mac mini M4 sí es un objeto identificado.
La carcasa no es un objeto identificado porque es la pieza que se generará.

Otro ejemplo:

"Necesito una caja de 100 x 80 x 40 mm"

No existe ningún objeto adicional.
La caja es la pieza que se generará y no debe aparecer como objeto identificado.

Otro ejemplo:

"Quiero una caja con cuatro soportes para una placa PCB"

La caja no debe aparecer en identified_objects.
La placa PCB sí debe aparecer en identified_objects porque es el objeto
que se alojará y fijará dentro de la caja.

Otro ejemplo:

"Necesito un soporte para una pantalla de 7 pulgadas"

El soporte no debe aparecer en identified_objects.
La pantalla sí debe aparecer en identified_objects.

Otro ejemplo:

"Necesito una carcasa para un ESP32-S3 con batería y altavoz"

La carcasa no debe aparecer en identified_objects.
El ESP32-S3, la batería y el altavoz sí deben aparecer en identified_objects.

No elimines un objeto de identified_objects solo porque no tenga fabricante
o modelo conocido.

Una placa PCB genérica, una batería, un motor, un altavoz, una pantalla,
un tornillo, un rodamiento o cualquier otro objeto físico relevante puede
aparecer en identified_objects aunque no sea un producto comercial concreto.

Para objetos genéricos sin fabricante o modelo:

- manufacturer debe ser null;
- model debe ser null;
- requires_web_research debe ser false, salvo que el usuario mencione un
  producto, placa o componente concreto cuya geometría deba investigarse.

No preguntes por:

- dimensiones oficiales;
- peso;
- ubicación de conectores;
- ventilación;
- planos;
- geometría;
- características publicadas por el fabricante.

Todo eso debe investigarse en Internet cuando corresponda.

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