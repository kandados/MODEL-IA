from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

import cadquery as cq

from src.models.mechanical_plan import MechanicalPlan


@dataclass(slots=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ValidationResult:
    is_valid: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "error"
        ]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [
            issue
            for issue in self.issues
            if issue.severity == "warning"
        ]

    def add_error(
        self,
        code: str,
        message: str,
        **context: Any,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                code=code,
                message=message,
                severity="error",
                context=context,
            )
        )
        self.is_valid = False

    def add_warning(
        self,
        code: str,
        message: str,
        **context: Any,
    ) -> None:
        self.issues.append(
            ValidationIssue(
                code=code,
                message=message,
                severity="warning",
                context=context,
            )
        )

    def merge(
        self,
        other: ValidationResult,
        *,
        source: str | None = None,
    ) -> None:
        """
        Incorpora los problemas de otra validación.

        Cuando se proporciona source, se añade esa referencia al contexto
        para identificar si el problema procede de la base, la tapa o
        el ensamblaje.
        """

        for issue in other.issues:
            context = dict(issue.context)

            if source is not None:
                context["source"] = source

            self.issues.append(
                ValidationIssue(
                    code=issue.code,
                    message=issue.message,
                    severity=issue.severity,
                    context=context,
                )
            )

        if not other.is_valid:
            self.is_valid = False


class CADValidationError(RuntimeError):
    def __init__(
        self,
        result: ValidationResult,
    ) -> None:
        self.result = result

        details = "; ".join(
            issue.message
            for issue in result.errors
        )

        super().__init__(
            details
            or "La pieza CAD no ha superado la validación."
        )


class CADValidator:
    DEFAULT_MINIMUM_DIMENSION_MM = 0.10
    DEFAULT_MINIMUM_VOLUME_MM3 = 0.01
    DEFAULT_MAXIMUM_DIMENSION_MM = 2_000.0

    def __init__(
        self,
        minimum_dimension_mm: float = DEFAULT_MINIMUM_DIMENSION_MM,
        minimum_volume_mm3: float = DEFAULT_MINIMUM_VOLUME_MM3,
        maximum_dimension_mm: float = DEFAULT_MAXIMUM_DIMENSION_MM,
    ) -> None:
        self.minimum_dimension_mm = minimum_dimension_mm
        self.minimum_volume_mm3 = minimum_volume_mm3
        self.maximum_dimension_mm = maximum_dimension_mm

    def validate(
        self,
        body: cq.Workplane | cq.Shape,
        plan: MechanicalPlan | None = None,
        *,
        allow_multiple_solids: bool = False,
    ) -> ValidationResult:
        """
        Valida geometría y, opcionalmente, el MechanicalPlan.

        allow_multiple_solids debe activarse únicamente para ensamblajes
        que estén formados deliberadamente por varias piezas.
        """

        result = ValidationResult(is_valid=True)

        if plan is not None:
            self._validate_plan(
                plan=plan,
                result=result,
            )

        shape = self._extract_shape(
            body=body,
            result=result,
        )

        if shape is not None:
            self._validate_shape(
                shape=shape,
                result=result,
                allow_multiple_solids=allow_multiple_solids,
            )

        return result

    def validate_or_raise(
        self,
        body: cq.Workplane | cq.Shape,
        plan: MechanicalPlan | None = None,
        *,
        allow_multiple_solids: bool = False,
    ) -> ValidationResult:
        result = self.validate(
            body=body,
            plan=plan,
            allow_multiple_solids=allow_multiple_solids,
        )

        if not result.is_valid:
            raise CADValidationError(result)

        return result

    def _validate_plan(
        self,
        plan: MechanicalPlan,
        result: ValidationResult,
    ) -> None:
        box = plan.external_bounding_box

        if box is None:
            result.add_error(
                "missing_external_bounding_box",
                "MechanicalPlan no contiene dimensiones exteriores.",
            )
            return

        dimensions = {
            "width_mm": box.width_mm,
            "depth_mm": box.depth_mm,
            "height_mm": box.height_mm,
        }

        for name, value in dimensions.items():
            if value <= self.minimum_dimension_mm:
                result.add_error(
                    "dimension_too_small",
                    f"La dimensión '{name}' es demasiado pequeña.",
                    value=value,
                )

            elif value > self.maximum_dimension_mm:
                result.add_warning(
                    "dimension_unusually_large",
                    f"La dimensión '{name}' es inusualmente grande.",
                    value=value,
                )

        self._validate_collection(
            value=plan.supports,
            name="supports",
            result=result,
        )

        self._validate_collection(
            value=plan.openings,
            name="openings",
            result=result,
        )

        self._validate_collection(
            value=plan.mount_features,
            name="mount_features",
            result=result,
        )

    @staticmethod
    def _validate_collection(
        value: object,
        name: str,
        result: ValidationResult,
    ) -> None:
        if (
            isinstance(value, (str, bytes))
            or not isinstance(value, Iterable)
        ):
            result.add_error(
                "invalid_plan_collection",
                f"'{name}' debe ser una colección iterable.",
            )

    @staticmethod
    def _extract_shape(
        body: cq.Workplane | cq.Shape,
        result: ValidationResult,
    ) -> cq.Shape | None:
        if isinstance(body, cq.Shape):
            return body

        if isinstance(body, cq.Workplane):
            try:
                value = body.val()
            except Exception as exc:
                result.add_error(
                    "workplane_value_error",
                    "No se pudo obtener la geometría del Workplane.",
                    exception=str(exc),
                )
                return None

            if isinstance(value, cq.Shape):
                return value

        result.add_error(
            "unsupported_body",
            "El objeto no contiene una geometría CadQuery válida.",
        )

        return None

    def _validate_shape(
        self,
        shape: cq.Shape,
        result: ValidationResult,
        *,
        allow_multiple_solids: bool,
    ) -> None:
        if shape.isNull():
            result.add_error(
                "null_shape",
                "La geometría generada es nula.",
            )
            return

        if not shape.isValid():
            result.add_error(
                "invalid_topology",
                "La geometría contiene errores topológicos.",
            )

        solids = list(shape.Solids())

        if not solids:
            result.add_error(
                "no_solids",
                "La geometría no contiene sólidos cerrados.",
            )
            return

        if (
            len(solids) > 1
            and not allow_multiple_solids
        ):
            result.add_warning(
                "multiple_solids",
                (
                    "La pieza contiene varios sólidos desconectados. "
                    "Puede existir geometría flotante o sin fusionar."
                ),
                solid_count=len(solids),
            )

        total_volume = sum(
            abs(solid.Volume())
            for solid in solids
        )

        if total_volume <= self.minimum_volume_mm3:
            result.add_error(
                "volume_too_small",
                "El volumen total de la geometría es insuficiente.",
                volume_mm3=total_volume,
            )

        box = shape.BoundingBox()

        dimensions = {
            "x_length_mm": box.xlen,
            "y_length_mm": box.ylen,
            "z_length_mm": box.zlen,
        }

        for name, value in dimensions.items():
            if value <= self.minimum_dimension_mm:
                result.add_error(
                    "bounding_dimension_too_small",
                    f"La dimensión '{name}' es demasiado pequeña.",
                    value=value,
                )