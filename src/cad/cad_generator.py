from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import cadquery as cq

from src.cad.enclosure_builder import EnclosureBuilder
from src.cad.enclosure_specification import EnclosureSpecification
from src.cad.export_manager import ExportManager, ExportResult
from src.cad.fastening_builder import FasteningBuilder
from src.cad.fillet_builder import FilletBuilder
from src.cad.opening_builder import OpeningBuilder
from src.cad.support_builder import SupportBuilder
from src.cad.validation import (
    CADValidationError,
    CADValidator,
    ValidationResult,
)
from src.models.mechanical_plan import MechanicalPlan


@dataclass(slots=True)
class CADGenerationResult:
    assembly: cq.Workplane
    print_layout: cq.Workplane
    base: cq.Workplane
    lid: cq.Workplane
    supports: cq.Workplane
    openings: cq.Workplane
    mount_features: cq.Workplane
    validation: ValidationResult
    exports: dict[str, ExportResult] | None = None


class CADGenerator:
    def __init__(
        self,
        enclosure_builder: EnclosureBuilder | None = None,
        support_builder: SupportBuilder | None = None,
        opening_builder: OpeningBuilder | None = None,
        fastening_builder: FasteningBuilder | None = None,
        fillet_builder: FilletBuilder | None = None,
        validator: CADValidator | None = None,
        export_manager: ExportManager | None = None,
    ) -> None:
        self.enclosure_builder = (
            enclosure_builder
            or EnclosureBuilder()
        )

        self.support_builder = (
            support_builder
            or SupportBuilder()
        )

        self.opening_builder = (
            opening_builder
            or OpeningBuilder()
        )

        self.fastening_builder = (
            fastening_builder
            or FasteningBuilder()
        )

        self.fillet_builder = (
            fillet_builder
            or FilletBuilder()
        )

        self.validator = (
            validator
            or CADValidator()
        )

        self.export_manager = (
            export_manager
            or ExportManager()
        )

    def generate(
        self,
        plan: MechanicalPlan,
        *,
        export: bool = False,
        file_name: str = "model_ia_part",
        formats: Iterable[str] = (
            "step",
            "stl",
            "3mf",
        ),
        output_directory: str | Path | None = None,
    ) -> CADGenerationResult:
        self._validate_plan_input(plan)
        specification = EnclosureSpecification.from_plan(plan)

        base = self.enclosure_builder.build_base(plan)
        lid = self.enclosure_builder.build_lid(plan)

        supports = self.support_builder.build(plan)
        openings = self.opening_builder.build(plan)
        mount_features = self.fastening_builder.build(plan)

        if self._contains_shape(supports):
            base = base.union(supports)

        if self._contains_shape(mount_features):
            base = base.union(mount_features)

        if self._contains_shape(openings):
            base = base.cut(openings)
            lid = lid.cut(openings)

        base = self.fillet_builder.apply(
            base,
            plan,
        )

        lid = self.fillet_builder.apply(
            lid,
            plan,
        )

        assembled_lid = lid.translate(
            (
                0.0,
                0.0,
                specification.base_height_mm,
            )
        )

        assembly = self._make_compound(
            base,
            assembled_lid,
        )

        print_layout = self._make_print_layout(
            base=base,
            lid=lid,
            width_mm=specification.external_box.width_mm,
        )

        validation = self._validate_generated_geometry(
            plan=plan,
            base=base,
            lid=lid,
            assembly=assembly,
        )

        exports: dict[str, ExportResult] | None = None

        if export:
            requested_formats = self.export_manager.normalize_formats(
                formats
            )
            exports = {}

            if "step" in requested_formats:
                exports["assembly"] = self.export_manager.export(
                    self._make_named_assembly(
                        base=base,
                        lid=lid,
                        lid_height_offset_mm=(
                            specification.base_height_mm
                        ),
                        name=file_name,
                    ),
                    file_name,
                    ("step",),
                    output_directory,
                )

            if "stl" in requested_formats:
                exports["base"] = self.export_manager.export(
                    base,
                    f"{file_name}_base",
                    ("stl",),
                    output_directory,
                )
                exports["lid"] = self.export_manager.export(
                    lid,
                    f"{file_name}_lid",
                    ("stl",),
                    output_directory,
                )

            if "3mf" in requested_formats:
                exports["print_layout"] = self.export_manager.export(
                    print_layout,
                    f"{file_name}_print_layout",
                    ("3mf",),
                    output_directory,
                )

        return CADGenerationResult(
            assembly=assembly,
            print_layout=print_layout,
            base=base,
            lid=lid,
            supports=supports,
            openings=openings,
            mount_features=mount_features,
            validation=validation,
            exports=exports,
        )

    def generate_and_export(
        self,
        plan: MechanicalPlan,
        file_name: str,
        *,
        formats: Iterable[str] = (
            "step",
            "stl",
            "3mf",
        ),
        output_directory: str | Path | None = None,
    ) -> CADGenerationResult:
        return self.generate(
            plan,
            export=True,
            file_name=file_name,
            formats=formats,
            output_directory=output_directory,
        )

    def _validate_generated_geometry(
        self,
        *,
        plan: MechanicalPlan,
        base: cq.Workplane,
        lid: cq.Workplane,
        assembly: cq.Workplane,
    ) -> ValidationResult:
        """
        Valida por separado las piezas fabricables y el ensamblaje.

        La base y la tapa deben ser sólidos únicos. El ensamblaje puede
        contener varias piezas separadas de forma deliberada.
        """

        combined_result = ValidationResult(
            is_valid=True
        )

        base_result = self.validator.validate(
            body=base,
            plan=plan,
            allow_multiple_solids=False,
        )

        combined_result.merge(
            base_result,
            source="base",
        )

        lid_result = self.validator.validate(
            body=lid,
            plan=None,
            allow_multiple_solids=False,
        )

        combined_result.merge(
            lid_result,
            source="lid",
        )

        assembly_result = self.validator.validate(
            body=assembly,
            plan=None,
            allow_multiple_solids=True,
        )

        combined_result.merge(
            assembly_result,
            source="assembly",
        )

        if not combined_result.is_valid:
            raise CADValidationError(
                combined_result
            )

        return combined_result

    @staticmethod
    def _make_compound(
        base: cq.Workplane,
        lid: cq.Workplane,
    ) -> cq.Workplane:
        base_shape = CADGenerator._extract_shape(
            base,
            "base",
        )

        lid_shape = CADGenerator._extract_shape(
            lid,
            "tapa",
        )

        compound = cq.Compound.makeCompound(
            [
                base_shape,
                lid_shape,
            ]
        )

        return cq.Workplane("XY").newObject(
            [compound]
        )

    @staticmethod
    def _make_print_layout(
        *,
        base: cq.Workplane,
        lid: cq.Workplane,
        width_mm: float,
        gap_mm: float = 5.0,
    ) -> cq.Workplane:
        """Coloca las piezas separadas y listas para laminar en 3MF."""

        center_offset_mm = (width_mm + gap_mm) / 2.0

        return CADGenerator._make_compound(
            base.translate((-center_offset_mm, 0.0, 0.0)),
            lid.translate((center_offset_mm, 0.0, 0.0)),
        )

    @staticmethod
    def _make_named_assembly(
        *,
        base: cq.Workplane,
        lid: cq.Workplane,
        lid_height_offset_mm: float,
        name: str,
    ) -> cq.Assembly:
        """Crea un STEP con base y tapa como componentes identificados."""

        assembly = cq.Assembly(name=name)
        assembly.add(base, name="base")
        assembly.add(
            lid,
            name="lid",
            loc=cq.Location(
                cq.Vector(
                    0.0,
                    0.0,
                    lid_height_offset_mm,
                )
            ),
        )
        return assembly

    @staticmethod
    def _extract_shape(
        workplane: cq.Workplane,
        name: str,
    ) -> cq.Shape:
        try:
            value = workplane.val()
        except Exception as exc:
            raise ValueError(
                f"No se pudo obtener la geometría de {name}."
            ) from exc

        if (
            not isinstance(value, cq.Shape)
            or value.isNull()
        ):
            raise ValueError(
                f"{name.capitalize()} no contiene geometría válida."
            )

        return value

    @staticmethod
    def _contains_shape(
        workplane: cq.Workplane,
    ) -> bool:
        try:
            return any(
                isinstance(value, cq.Shape)
                for value in workplane.vals()
            )
        except Exception:
            return False

    @staticmethod
    def _validate_plan_input(
        plan: MechanicalPlan,
    ) -> None:
        if not isinstance(
            plan,
            MechanicalPlan,
        ):
            raise TypeError(
                "'plan' debe ser una instancia de MechanicalPlan."
            )

        if plan.external_bounding_box is None:
            raise ValueError(
                "MechanicalPlan debe contener "
                "external_bounding_box."
            )
