from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cadquery as cq
from cadquery import exporters


@dataclass(slots=True, frozen=True)
class ExportedFile:
    """Describe un archivo CAD exportado."""

    format: str
    path: Path


@dataclass(slots=True)
class ExportResult:
    """Resultado estructurado de una operación de exportación."""

    files: list[ExportedFile]

    def get(self, format_name: str) -> Path | None:
        normalized = format_name.strip().lower()

        for exported_file in self.files:
            if exported_file.format == normalized:
                return exported_file.path

        return None


class ExportManager:
    """Gestiona la exportación de geometría CadQuery."""

    SUPPORTED_FORMATS = ("step", "stl", "3mf")

    def __init__(
        self,
        output_directory: str | Path = "projects/generated",
    ) -> None:
        self.output_directory = Path(output_directory)

    def export(
        self,
        body: cq.Workplane | cq.Shape,
        file_name: str,
        formats: Iterable[str] = SUPPORTED_FORMATS,
        output_directory: str | Path | None = None,
    ) -> ExportResult:
        shape = self._extract_shape(body)
        safe_name = self._sanitize_file_name(file_name)
        target_directory = self._prepare_directory(output_directory)

        requested_formats = self._normalize_formats(formats)
        exported_files: list[ExportedFile] = []

        for format_name in requested_formats:
            output_path = target_directory / f"{safe_name}.{format_name}"
            self._export_shape(shape, output_path, format_name)
            exported_files.append(
                ExportedFile(
                    format=format_name,
                    path=output_path,
                )
            )

        return ExportResult(files=exported_files)

    def export_step(
        self,
        body: cq.Workplane | cq.Shape,
        file_name: str,
        output_directory: str | Path | None = None,
    ) -> Path:
        return self.export(
            body=body,
            file_name=file_name,
            formats=("step",),
            output_directory=output_directory,
        ).files[0].path

    def export_stl(
        self,
        body: cq.Workplane | cq.Shape,
        file_name: str,
        output_directory: str | Path | None = None,
    ) -> Path:
        return self.export(
            body=body,
            file_name=file_name,
            formats=("stl",),
            output_directory=output_directory,
        ).files[0].path

    def export_3mf(
        self,
        body: cq.Workplane | cq.Shape,
        file_name: str,
        output_directory: str | Path | None = None,
    ) -> Path:
        return self.export(
            body=body,
            file_name=file_name,
            formats=("3mf",),
            output_directory=output_directory,
        ).files[0].path

    def _export_shape(
        self,
        shape: cq.Shape,
        output_path: Path,
        format_name: str,
    ) -> None:
        try:
            if format_name == "step":
                exporters.export(
                    shape,
                    str(output_path),
                    exportType=exporters.ExportTypes.STEP,
                )
                return

            if format_name == "stl":
                exporters.export(
                    shape,
                    str(output_path),
                    exportType=exporters.ExportTypes.STL,
                    tolerance=0.01,
                    angularTolerance=0.1,
                )
                return

            if format_name == "3mf":
                exporters.export(
                    shape,
                    str(output_path),
                    exportType=exporters.ExportTypes.THREEMF,
                )
                return

        except Exception as exc:
            raise RuntimeError(
                f"No se pudo exportar '{output_path.name}': {exc}"
            ) from exc

        raise ValueError(f"Formato de exportación no soportado: {format_name}")

    def _prepare_directory(
        self,
        output_directory: str | Path | None,
    ) -> Path:
        directory = (
            Path(output_directory)
            if output_directory is not None
            else self.output_directory
        )

        directory.mkdir(parents=True, exist_ok=True)
        return directory.resolve()

    @staticmethod
    def _extract_shape(
        body: cq.Workplane | cq.Shape,
    ) -> cq.Shape:
        if isinstance(body, cq.Shape):
            shape = body
        elif isinstance(body, cq.Workplane):
            try:
                shape = body.val()
            except Exception as exc:
                raise ValueError(
                    "No se pudo obtener la geometría del Workplane."
                ) from exc
        else:
            raise TypeError(
                "El objeto recibido debe ser un Workplane o Shape de CadQuery."
            )

        if not isinstance(shape, cq.Shape):
            raise ValueError(
                "El objeto recibido no contiene una geometría CadQuery válida."
            )

        if shape.isNull():
            raise ValueError("No se puede exportar una geometría nula.")

        return shape

    @classmethod
    def _normalize_formats(
        cls,
        formats: Iterable[str],
    ) -> tuple[str, ...]:
        normalized: list[str] = []

        for format_name in formats:
            value = format_name.strip().lower().lstrip(".")

            if value not in cls.SUPPORTED_FORMATS:
                raise ValueError(
                    f"Formato no soportado: {format_name}. "
                    f"Formatos válidos: {', '.join(cls.SUPPORTED_FORMATS)}."
                )

            if value not in normalized:
                normalized.append(value)

        if not normalized:
            raise ValueError(
                "Debe indicarse al menos un formato de exportación."
            )

        return tuple(normalized)

    @staticmethod
    def _sanitize_file_name(file_name: str) -> str:
        value = file_name.strip()

        if not value:
            raise ValueError("El nombre del archivo no puede estar vacío.")

        for suffix in (".step", ".stl", ".3mf"):
            if value.lower().endswith(suffix):
                value = value[: -len(suffix)]
                break

        safe_characters: list[str] = []

        for character in value:
            if character.isalnum() or character in ("-", "_"):
                safe_characters.append(character)
            elif character.isspace():
                safe_characters.append("_")

        safe_name = "".join(safe_characters).strip("_")

        if not safe_name:
            raise ValueError(
                "El nombre del archivo no contiene caracteres válidos."
            )

        return safe_name