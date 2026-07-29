from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import ValidationError

from src.models.design_request import DesignRequest
from src.models.research_report import ResearchReport


RESEARCH_INSTRUCTIONS = """
Eres el investigador técnico de Model-IA.

Model-IA es un ingeniero mecánico autónomo que necesita investigar objetos
físicos reales antes de diseñar piezas para ellos.

Debes investigar en Internet los objetos indicados en la petición.

OBJETIVOS

1. Confirmar la identidad exacta de cada producto.
2. Buscar primero documentación oficial del fabricante.
3. Obtener dimensiones exteriores y peso.
4. Investigar geometría exterior relevante.
5. Localizar puertos, botones, conectores y elementos que deban quedar accesibles.
6. Investigar ventilación, entradas y salidas de aire.
7. Buscar planos dimensionales, manuales técnicos y modelos CAD disponibles.
8. Detectar contradicciones entre fuentes.
9. Indicar claramente los datos que no puedan confirmarse.
10. Asignar un nivel de confianza realista a cada dato.

ESTRUCTURA DE FUENTES

- Cada fuente debe incluir un identificador único llamado "source_id".
- Los identificadores deben seguir este formato:

  SRC-001
  SRC-002
  SRC-003

- Cada fuente debe aparecer una sola vez dentro de "sources".
- Los datos técnicos no deben repetir las URL.
- Cada dato técnico debe usar "source_ids" para indicar qué fuentes lo respaldan.
- Todos los identificadores usados en "source_ids" deben existir en "sources".
- No reutilices el mismo source_id para dos fuentes distintas.

EVIDENCIAS

- Cada dato técnico debe incluir un campo "evidence".
- La evidencia debe explicar brevemente qué información concreta de la fuente
  respalda el dato.
- No copies párrafos completos.
- No inventes citas textuales.
- Si la fuente solo permite una inferencia, indícalo claramente.
- La evidencia debe ser breve, precisa y útil para auditoría.

PRIORIDAD DE FUENTES

1. Página oficial del fabricante.
2. Documentación oficial del fabricante.
3. Manual oficial.
4. Plano técnico oficial.
5. Modelo CAD oficial.
6. Distribuidor técnico fiable.
7. Base de datos técnica reconocida.
8. Fuente comunitaria.

REGLAS DE CONFIANZA

- Utiliza una confianza alta para datos numéricos confirmados por el fabricante.
- Reduce la confianza cuando el dato provenga únicamente de una fuente secundaria.
- Reduce la confianza cuando el dato sea una inferencia visual o geométrica.
- Si hay contradicciones, registra el conflicto y reduce la confianza.
- No uses confianza 1.0 salvo que el dato sea inequívoco y esté confirmado
  directamente por varias fuentes fiables.

REGLAS GENERALES

- No inventes dimensiones.
- No inventes posiciones.
- No inventes radios.
- No conviertas una aproximación visual en una cota exacta.
- No presentes una fuente comunitaria como oficial.
- No afirmes que un recurso no existe: indica únicamente que no fue encontrado.
- Distingue el cuerpo principal de salientes, patas, conectores y cables.
- Usa milímetros para dimensiones siempre que sea posible.
- No diseñes todavía ninguna pieza.
- No tomes decisiones de CAD.
- Devuelve únicamente un objeto JSON válido compatible con el esquema recibido.
"""


class WebResearchError(RuntimeError):
    """Error controlado durante la investigación web."""


class WebResearcher:
    """Investiga objetos físicos reales y devuelve información estructurada."""

    def __init__(
        self,
        model: str = "gpt-5.5",
    ) -> None:
        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise WebResearchError(
                "No se encontró OPENAI_API_KEY en el archivo .env."
            )

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def research(
        self,
        design_request: DesignRequest,
    ) -> ResearchReport:
        objects_to_research = [
            identified_object
            for identified_object in design_request.identified_objects
            if identified_object.requires_web_research
        ]

        researched_at = datetime.now(timezone.utc).isoformat()

        if not objects_to_research:
            return ResearchReport(
                original_request=design_request.original_request,
                researched_at=researched_at,
                researched_objects=[],
                research_complete=True,
                missing_critical_information=[],
                report_summary=(
                    "La petición no contiene objetos que requieran "
                    "investigación web."
                ),
            )

        research_input = {
            "original_request": design_request.original_request,
            "objects_to_research": [
                identified_object.model_dump()
                for identified_object in objects_to_research
            ],
            "information_requested": (
                design_request.information_to_research
            ),
            "researched_at": researched_at,
        }

        schema = ResearchReport.model_json_schema()

        prompt = f"""
Investiga técnicamente los siguientes objetos físicos.

DATOS DE ENTRADA

{json.dumps(research_input, ensure_ascii=False, indent=2)}

INSTRUCCIONES ADICIONALES

- Usa exactamente el valor de "researched_at" proporcionado en los datos
  de entrada.
- No generes una fecha distinta.
- Cada fuente debe tener un source_id único.
- Cada TechnicalFact debe usar source_ids.
- No incluyas source_urls.
- Todos los source_ids referenciados deben existir en la lista sources.
- Devuelve exclusivamente un objeto JSON.

ESQUEMA JSON OBLIGATORIO

{json.dumps(schema, ensure_ascii=False, indent=2)}
"""

        try:
            response = self.client.responses.create(
                model=self.model,
                tools=[
                    {
                        "type": "web_search_preview",
                    }
                ],
                instructions=RESEARCH_INSTRUCTIONS,
                input=prompt,
            )

        except Exception as exc:
            raise WebResearchError(
                "No se pudo realizar la investigación web.\n\n"
                f"{exc}"
            ) from exc

        raw_output = response.output_text.strip()

        if not raw_output:
            raise WebResearchError(
                "El investigador devolvió una respuesta vacía."
            )

        raw_output = self._remove_markdown_code_fence(raw_output)

        try:
            parsed_json = json.loads(raw_output)

        except json.JSONDecodeError as exc:
            raise WebResearchError(
                "El investigador no devolvió un JSON válido.\n\n"
                f"Respuesta recibida:\n{raw_output}"
            ) from exc

        parsed_json["researched_at"] = researched_at

        try:
            return ResearchReport.model_validate(parsed_json)

        except ValidationError as exc:
            raise WebResearchError(
                "La investigación no cumple la estructura esperada.\n\n"
                f"{exc}\n\n"
                f"Respuesta recibida:\n{raw_output}"
            ) from exc

    @staticmethod
    def _remove_markdown_code_fence(raw_output: str) -> str:
        """
        Elimina bloques Markdown del tipo ```json ... ```.

        El investigador tiene instrucciones para devolver JSON puro, pero esta
        limpieza evita errores cuando el modelo añade accidentalmente un bloque
        de código.
        """

        cleaned_output = raw_output.strip()

        if cleaned_output.startswith("```json"):
            cleaned_output = cleaned_output.removeprefix("```json").strip()

        elif cleaned_output.startswith("```"):
            cleaned_output = cleaned_output.removeprefix("```").strip()

        if cleaned_output.endswith("```"):
            cleaned_output = cleaned_output.removesuffix("```").strip()

        return cleaned_output