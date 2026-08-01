from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Literal
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, HTTPException, WebSocket
from fastapi import WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field

from src.agent.design_agent import DesignAgentError
from src.cad.enclosure_specification import EnclosureSpecification
from src.cad.validation import CADValidationError
from src.generation_service import (
    GenerationPipeline,
    GenerationPipelineResult,
    GenerationProgress,
    determine_material,
    determine_tolerance_mm,
)
from src.research.web_researcher import WebResearchError


LOGGER = logging.getLogger("model_ia.api")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
GENERATIONS_ROOT = PROJECT_ROOT / "projects" / "generated" / "api"
MAX_RETAINED_JOBS = 50


class GenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=20_000)
    attachment_names: list[str] = Field(default_factory=list)
    requested_formats: list[Literal["STEP", "STL", "3MF"]] = Field(
        default_factory=lambda: ["STEP", "STL", "3MF"]
    )


@dataclass(slots=True)
class GenerationJob:
    generation_id: str
    project_id: str
    output_directory: Path
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    events: list[dict[str, object]] = field(default_factory=list)
    terminal: bool = False


app = FastAPI(
    title="Model-IA API",
    version="1.0.0",
    description="Puente local entre Electron y el pipeline CAD de Model-IA.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "null",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Accept", "Content-Type"],
)

_jobs: dict[str, GenerationJob] = {}
_jobs_lock = Lock()


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "model-ia",
        "api_version": "v1",
    }


@app.post(
    "/api/v1/generations",
    status_code=status.HTTP_202_ACCEPTED,
)
def create_generation(
    request: GenerationRequest,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    generation_id = f"gen_{uuid4().hex}"
    job = GenerationJob(
        generation_id=generation_id,
        project_id=request.project_id,
        output_directory=GENERATIONS_ROOT / generation_id,
    )

    with _jobs_lock:
        _discard_old_jobs_if_required()
        _jobs[generation_id] = job

    background_tasks.add_task(
        _execute_generation,
        job,
        request,
    )

    return {
        "generation_id": generation_id,
        "websocket_url": (
            f"/api/v1/generations/{generation_id}/events"
        ),
    }


@app.websocket("/api/v1/generations/{generation_id}/events")
async def generation_events(
    websocket: WebSocket,
    generation_id: str,
) -> None:
    job = _get_job(generation_id)

    if job is None:
        await websocket.close(code=4404, reason="Generación no encontrada")
        return

    await websocket.accept()
    next_event_index = 0

    try:
        while True:
            events, terminal = _read_job_events(
                job,
                start_index=next_event_index,
            )

            for event in events:
                await websocket.send_json(event)
                next_event_index += 1

            if terminal and next_event_index >= len(job.events):
                break

            await asyncio.sleep(0.10)
    except WebSocketDisconnect:
        return
    finally:
        try:
            await websocket.close()
        except RuntimeError:
            pass


@app.get("/api/v1/generations/{generation_id}/files/{file_name}")
def download_generation_file(
    generation_id: str,
    file_name: str,
) -> FileResponse:
    if re.fullmatch(r"gen_[0-9a-f]{32}", generation_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Generación no encontrada.",
        )

    generation_directory = (GENERATIONS_ROOT / generation_id).resolve()
    candidate = (generation_directory / file_name).resolve()

    if candidate.parent != generation_directory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo no encontrado.",
        )

    if not candidate.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Archivo no encontrado.",
        )

    return FileResponse(
        path=candidate,
        filename=candidate.name,
    )


def _execute_generation(
    job: GenerationJob,
    request: GenerationRequest,
) -> None:
    try:
        pipeline_result = GenerationPipeline().run(
            request.message,
            requested_formats=request.requested_formats,
            output_directory=job.output_directory,
            on_progress=lambda progress: _append_progress(job, progress),
        )
        result = _serialize_result(
            job=job,
            request=request,
            pipeline_result=pipeline_result,
        )
        _append_event(
            job,
            {
                "type": "completed",
                "result": result,
            },
            terminal=True,
        )
    except Exception as exc:
        LOGGER.exception(
            "La generación %s ha fallado",
            job.generation_id,
        )
        _append_event(
            job,
            {
                "type": "failed",
                "message": _public_error_message(exc),
            },
            terminal=True,
        )


def _serialize_result(
    *,
    job: GenerationJob,
    request: GenerationRequest,
    pipeline_result: GenerationPipelineResult,
) -> dict[str, object]:
    box = pipeline_result.mechanical_plan.external_bounding_box

    if box is None:
        raise ValueError(
            "El plan mecánico no contiene dimensiones exteriores."
        )

    exports = pipeline_result.cad_result.exports or {}
    artifacts: list[dict[str, object]] = []

    step_file = _find_exported_file(exports, "assembly", "step")
    base_stl = _find_exported_file(exports, "base", "stl")
    lid_stl = _find_exported_file(exports, "lid", "stl")
    print_layout = _find_exported_file(
        exports,
        "print_layout",
        "3mf",
    )

    if step_file is not None:
        artifacts.append(
            _serialize_artifact(
                format_name="STEP",
                files=[
                    _serialize_exported_file(
                        job=job,
                        exported_file=step_file,
                        part_id="assembly",
                        label="Ensamblaje",
                    )
                ],
            )
        )

    stl_files = []
    if base_stl is not None:
        stl_files.append(
            _serialize_exported_file(
                job=job,
                exported_file=base_stl,
                part_id="base",
                label="Base",
            )
        )
    if lid_stl is not None:
        stl_files.append(
            _serialize_exported_file(
                job=job,
                exported_file=lid_stl,
                part_id="lid",
                label="Tapa",
            )
        )
    if stl_files:
        artifacts.append(
            _serialize_artifact(
                format_name="STL",
                files=stl_files,
            )
        )

    if print_layout is not None:
        artifacts.append(
            _serialize_artifact(
                format_name="3MF",
                files=[
                    _serialize_exported_file(
                        job=job,
                        exported_file=print_layout,
                        part_id="print_layout",
                        label="Base y tapa para imprimir",
                    )
                ],
            )
        )

    validations: list[dict[str, str]] = [
        {
            "id": "valid_geometry",
            "label": "Geometría CAD válida",
            "status": "passed",
        },
        {
            "id": "manufacturing_files",
            "label": "Archivos de fabricación preparados",
            "status": "passed",
        },
    ]

    for index, issue in enumerate(
        pipeline_result.cad_result.validation.warnings,
        start=1,
    ):
        validations.append(
            {
                "id": issue.code or f"warning_{index}",
                "label": issue.message,
                "status": "warning",
            }
        )

    result: dict[str, object] = {
        "generation_id": job.generation_id,
        "project_id": request.project_id,
        "status": "completed",
        "specification": {
            "dimensions": {
                "width_mm": box.width_mm,
                "depth_mm": box.depth_mm,
                "height_mm": box.height_mm,
            },
            "material": determine_material(
                pipeline_result.design_request
            ),
            "tolerance_mm": determine_tolerance_mm(
                pipeline_result.design_request
            ),
        },
        "validations": validations,
        "artifacts": artifacts,
    }

    if base_stl is not None and lid_stl is not None:
        specification = EnclosureSpecification.from_plan(
            pipeline_result.mechanical_plan
        )
        exploded_offset_mm = (
            specification.external_box.width_mm + 5.0
        ) / 2.0
        result["preview"] = {
            "format": "STL",
            "parts": [
                {
                    **_serialize_exported_file(
                        job=job,
                        exported_file=base_stl,
                        part_id="base",
                        label="Base",
                    ),
                    "id": "base",
                    "url": _file_url(job, base_stl.path.name),
                    "assembled_position_mm": [0.0, 0.0, 0.0],
                    "exploded_position_mm": [
                        -exploded_offset_mm,
                        0.0,
                        0.0,
                    ],
                },
                {
                    **_serialize_exported_file(
                        job=job,
                        exported_file=lid_stl,
                        part_id="lid",
                        label="Tapa",
                    ),
                    "id": "lid",
                    "url": _file_url(job, lid_stl.path.name),
                    "assembled_position_mm": [
                        0.0,
                        0.0,
                        specification.base_height_mm,
                    ],
                    "exploded_position_mm": [
                        exploded_offset_mm,
                        0.0,
                        0.0,
                    ],
                },
            ],
        }

    return result


def _find_exported_file(
    exports: dict[str, object],
    export_name: str,
    format_name: str,
):
    export_result = exports.get(export_name)

    for exported_file in getattr(export_result, "files", []):
        if exported_file.format.lower() == format_name.lower():
            return exported_file

    return None


def _file_url(job: GenerationJob, file_name: str) -> str:
    return (
        f"/api/v1/generations/{job.generation_id}/files/"
        f"{file_name}"
    )


def _serialize_exported_file(
    *,
    job: GenerationJob,
    exported_file,
    part_id: str,
    label: str,
) -> dict[str, object]:
    return {
        "part_id": part_id,
        "label": label,
        "file_name": exported_file.path.name,
        "download_url": _file_url(job, exported_file.path.name),
    }


def _serialize_artifact(
    *,
    format_name: str,
    files: list[dict[str, object]],
) -> dict[str, object]:
    if len(files) == 1:
        display_name = str(files[0]["file_name"])
    else:
        display_name = " + ".join(
            str(file_data["file_name"])
            for file_data in files
        )

    artifact: dict[str, object] = {
        "format": format_name,
        "file_name": display_name,
        "available": True,
        "files": files,
    }

    if len(files) == 1:
        artifact["download_url"] = files[0]["download_url"]

    return artifact


def _append_progress(
    job: GenerationJob,
    progress: GenerationProgress,
) -> None:
    _append_event(
        job,
        {
            "type": "progress",
            "stage": progress.stage,
            "stage_index": progress.stage_index,
            "progress": progress.progress,
            "message": progress.message,
        },
    )


def _append_event(
    job: GenerationJob,
    event: dict[str, object],
    *,
    terminal: bool = False,
) -> None:
    with _jobs_lock:
        job.events.append(event)

        if terminal:
            job.terminal = True


def _read_job_events(
    job: GenerationJob,
    *,
    start_index: int,
) -> tuple[list[dict[str, object]], bool]:
    with _jobs_lock:
        return list(job.events[start_index:]), job.terminal


def _get_job(generation_id: str) -> GenerationJob | None:
    with _jobs_lock:
        return _jobs.get(generation_id)


def _discard_old_jobs_if_required() -> None:
    if len(_jobs) < MAX_RETAINED_JOBS:
        return

    terminal_jobs = sorted(
        (
            job
            for job in _jobs.values()
            if job.terminal
        ),
        key=lambda candidate: candidate.created_at,
    )

    if terminal_jobs:
        _jobs.pop(terminal_jobs[0].generation_id, None)


def _public_error_message(exc: Exception) -> str:
    if isinstance(exc, DesignAgentError):
        return f"No se pudo interpretar la petición: {exc}"

    if isinstance(exc, WebResearchError):
        return f"No se pudo completar la investigación técnica: {exc}"

    if isinstance(exc, CADValidationError):
        details = "; ".join(
            issue.message
            for issue in exc.result.errors
        )
        return details or "La geometría CAD no superó la validación."

    if isinstance(exc, ValueError):
        return str(exc) or "La petición contiene datos no válidos."

    return (
        "El backend no pudo completar la generación. "
        f"Detalle técnico: {type(exc).__name__}: {str(exc) or '<sin mensaje>'}"
    )
