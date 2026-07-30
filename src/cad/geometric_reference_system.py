from __future__ import annotations

from dataclasses import dataclass

from src.cad.enclosure_specification import EnclosureSpecification
from src.models.mechanical_plan import (
    BoundingBox,
    ComponentPlacement,
    GeometricAnchor,
    InteriorMargins,
    MechanicalPlan,
    Point3D,
)


@dataclass(frozen=True)
class AxisAlignedVolume:
    """
    Volumen rectangular alineado con los ejes globales.
    """

    min_x_mm: float
    max_x_mm: float

    min_y_mm: float
    max_y_mm: float

    min_z_mm: float
    max_z_mm: float

    @property
    def width_mm(self) -> float:
        return self.max_x_mm - self.min_x_mm

    @property
    def depth_mm(self) -> float:
        return self.max_y_mm - self.min_y_mm

    @property
    def height_mm(self) -> float:
        return self.max_z_mm - self.min_z_mm

    @property
    def center(self) -> Point3D:
        return Point3D(
            x_mm=(self.min_x_mm + self.max_x_mm) / 2.0,
            y_mm=(self.min_y_mm + self.max_y_mm) / 2.0,
            z_mm=(self.min_z_mm + self.max_z_mm) / 2.0,
        )

    @property
    def bounding_box(self) -> BoundingBox:
        return BoundingBox(
            width_mm=self.width_mm,
            depth_mm=self.depth_mm,
            height_mm=self.height_mm,
        )


@dataclass(frozen=True)
class ResolvedPlacement:
    """
    Resultado de convertir una colocación paramétrica en coordenadas CAD.
    """

    target: str
    anchor: GeometricAnchor
    position: Point3D
    rotation_z_deg: float
    clearance_mm: float


class GeometricReferenceSystem:
    """
    Sistema común de coordenadas y referencias de una carcasa.

    Convención:

    - X positivo: derecha.
    - Y positivo: parte trasera.
    - Z positivo: arriba.
    - Origen global: centro de la cara inferior exterior.
    - La carcasa está centrada en X e Y.
    - La geometría empieza en Z=0.
    """

    def __init__(
        self,
        plan: MechanicalPlan,
        specification: EnclosureSpecification | None = None,
    ) -> None:
        self._plan = plan

        self._specification = (
            specification
            if specification is not None
            else EnclosureSpecification.from_plan(plan)
        )

        self._external_box = self._specification.external_box

        self._physical_interior = self._calculate_physical_interior()

        self._usable_interior = self._calculate_usable_interior(
            margins=self._plan.interior_margins,
        )

        self._anchors = self._build_anchors()

    @property
    def specification(self) -> EnclosureSpecification:
        return self._specification

    @property
    def external_box(self) -> BoundingBox:
        return self._external_box

    @property
    def base_height_mm(self) -> float:
        return self._specification.base_height_mm

    @property
    def wall_thickness_mm(self) -> float:
        return self._specification.wall_thickness_mm

    @property
    def physical_interior(self) -> AxisAlignedVolume:
        return self._physical_interior

    @property
    def usable_interior(self) -> AxisAlignedVolume:
        return self._usable_interior

    @property
    def anchors(self) -> dict[GeometricAnchor, Point3D]:
        return dict(self._anchors)

    def get_anchor(
        self,
        anchor: GeometricAnchor,
    ) -> Point3D:
        try:
            return self._anchors[anchor]
        except KeyError as error:
            raise ValueError(
                f"Anclaje geométrico no reconocido: {anchor}"
            ) from error

    def resolve_placement(
        self,
        placement: ComponentPlacement,
    ) -> ResolvedPlacement:
        anchor = self.get_anchor(placement.anchor)

        position = Point3D(
            x_mm=anchor.x_mm + placement.offset.x_mm,
            y_mm=anchor.y_mm + placement.offset.y_mm,
            z_mm=anchor.z_mm + placement.offset.z_mm,
        )

        return ResolvedPlacement(
            target=placement.target,
            anchor=placement.anchor,
            position=position,
            rotation_z_deg=placement.rotation_z_deg,
            clearance_mm=placement.clearance_mm,
        )

    def resolve_all_placements(
        self,
    ) -> list[ResolvedPlacement]:
        return [
            self.resolve_placement(placement)
            for placement in self._plan.component_placements
        ]

    def contains_point(
        self,
        point: Point3D,
        use_usable_volume: bool = True,
    ) -> bool:
        volume = (
            self._usable_interior
            if use_usable_volume
            else self._physical_interior
        )

        return (
            volume.min_x_mm <= point.x_mm <= volume.max_x_mm
            and volume.min_y_mm <= point.y_mm <= volume.max_y_mm
            and volume.min_z_mm <= point.z_mm <= volume.max_z_mm
        )

    def _calculate_physical_interior(
        self,
    ) -> AxisAlignedVolume:
        half_width = self._external_box.width_mm / 2.0
        half_depth = self._external_box.depth_mm / 2.0

        wall = self._specification.wall_thickness_mm

        return AxisAlignedVolume(
            min_x_mm=-half_width + wall,
            max_x_mm=half_width - wall,
            min_y_mm=-half_depth + wall,
            max_y_mm=half_depth - wall,
            min_z_mm=wall,
            max_z_mm=self._specification.base_height_mm,
        )

    def _calculate_usable_interior(
        self,
        margins: InteriorMargins,
    ) -> AxisAlignedVolume:
        volume = AxisAlignedVolume(
            min_x_mm=(
                self._physical_interior.min_x_mm
                + margins.left_mm
            ),
            max_x_mm=(
                self._physical_interior.max_x_mm
                - margins.right_mm
            ),
            min_y_mm=(
                self._physical_interior.min_y_mm
                + margins.front_mm
            ),
            max_y_mm=(
                self._physical_interior.max_y_mm
                - margins.rear_mm
            ),
            min_z_mm=(
                self._physical_interior.min_z_mm
                + margins.floor_mm
            ),
            max_z_mm=(
                self._physical_interior.max_z_mm
                - margins.ceiling_mm
            ),
        )

        self._validate_volume(
            volume,
            name="volumen interior útil",
        )

        return volume

    def _build_anchors(
        self,
    ) -> dict[GeometricAnchor, Point3D]:
        usable = self._usable_interior
        external = self._external_box
        center = usable.center

        return {
            "global_origin": Point3D(
                x_mm=0.0,
                y_mm=0.0,
                z_mm=0.0,
            ),
            "external_center": Point3D(
                x_mm=0.0,
                y_mm=0.0,
                z_mm=external.height_mm / 2.0,
            ),
            "interior_center": center,
            "floor_center": Point3D(
                x_mm=center.x_mm,
                y_mm=center.y_mm,
                z_mm=usable.min_z_mm,
            ),
            "ceiling_center": Point3D(
                x_mm=center.x_mm,
                y_mm=center.y_mm,
                z_mm=usable.max_z_mm,
            ),
            "left_wall_center": Point3D(
                x_mm=usable.min_x_mm,
                y_mm=center.y_mm,
                z_mm=center.z_mm,
            ),
            "right_wall_center": Point3D(
                x_mm=usable.max_x_mm,
                y_mm=center.y_mm,
                z_mm=center.z_mm,
            ),
            "front_wall_center": Point3D(
                x_mm=center.x_mm,
                y_mm=usable.min_y_mm,
                z_mm=center.z_mm,
            ),
            "rear_wall_center": Point3D(
                x_mm=center.x_mm,
                y_mm=usable.max_y_mm,
                z_mm=center.z_mm,
            ),
            "bottom_left": Point3D(
                x_mm=usable.min_x_mm,
                y_mm=usable.min_y_mm,
                z_mm=usable.min_z_mm,
            ),
            "bottom_right": Point3D(
                x_mm=usable.max_x_mm,
                y_mm=usable.min_y_mm,
                z_mm=usable.min_z_mm,
            ),
            "top_left": Point3D(
                x_mm=usable.min_x_mm,
                y_mm=usable.max_y_mm,
                z_mm=usable.min_z_mm,
            ),
            "top_right": Point3D(
                x_mm=usable.max_x_mm,
                y_mm=usable.max_y_mm,
                z_mm=usable.min_z_mm,
            ),
        }

    @staticmethod
    def _validate_volume(
        volume: AxisAlignedVolume,
        name: str,
    ) -> None:
        if volume.width_mm <= 0:
            raise ValueError(
                f"El {name} no tiene ancho positivo."
            )

        if volume.depth_mm <= 0:
            raise ValueError(
                f"El {name} no tiene profundidad positiva."
            )

        if volume.height_mm <= 0:
            raise ValueError(
                f"El {name} no tiene altura positiva."
            )