from __future__ import annotations

from dataclasses import dataclass
from math import isclose

from src.cad.geometric_reference_system import (
    AxisAlignedVolume,
    GeometricReferenceSystem,
    ResolvedPlacement,
)
from src.models.mechanical_plan import (
    ComponentDimensions,
    ComponentPlacement,
    MechanicalPlan,
    Point3D,
    ReservedZone,
)


@dataclass(frozen=True)
class PlacementIssue:
    """
    Problema detectado durante la planificación geométrica.
    """

    code: str
    target: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class PlacedComponent:
    """
    Componente cuya posición y volumen ocupado ya han sido resueltos.
    """

    target: str

    source: ComponentPlacement

    resolved: ResolvedPlacement

    occupied_volume: AxisAlignedVolume

    dimensions: ComponentDimensions


@dataclass(frozen=True)
class ResolvedReservedZone:
    """
    Zona reservada convertida en un volumen cartesiano real.
    """

    name: str
    reason: str
    occupied_volume: AxisAlignedVolume


@dataclass(frozen=True)
class PlacementPlan:
    """
    Resultado completo del planificador de colocación.
    """

    components: list[PlacedComponent]

    reserved_zones: list[ResolvedReservedZone]

    issues: list[PlacementIssue]

    @property
    def is_valid(self) -> bool:
        return not any(
            issue.severity == "error"
            for issue in self.issues
        )


class PlacementPlanner:
    """
    Convierte colocaciones paramétricas en volúmenes cartesianos.

    Responsabilidades:

    - resolver anclajes;
    - aplicar offsets;
    - aplicar rotaciones ortogonales;
    - calcular el volumen ocupado;
    - validar límites interiores;
    - comprobar zonas reservadas;
    - comprobar colisiones entre componentes.

    No genera geometría CAD.
    """

    ORTHOGONAL_ROTATIONS = (
        0.0,
        90.0,
        180.0,
        270.0,
    )

    def build(
        self,
        plan: MechanicalPlan,
        references: GeometricReferenceSystem | None = None,
    ) -> PlacementPlan:
        reference_system = (
            references
            if references is not None
            else GeometricReferenceSystem(plan)
        )

        issues: list[PlacementIssue] = []

        reserved_zones = self._resolve_reserved_zones(
            plan=plan,
            references=reference_system,
            issues=issues,
        )

        components = self._resolve_components(
            plan=plan,
            references=reference_system,
            issues=issues,
        )

        self._check_component_collisions(
            components=components,
            issues=issues,
        )

        self._check_reserved_zone_collisions(
            components=components,
            reserved_zones=reserved_zones,
            issues=issues,
        )

        return PlacementPlan(
            components=components,
            reserved_zones=reserved_zones,
            issues=issues,
        )

    def require_valid(
        self,
        plan: MechanicalPlan,
        references: GeometricReferenceSystem | None = None,
    ) -> PlacementPlan:
        """
        Genera un PlacementPlan y lanza una excepción si contiene errores.
        """

        placement_plan = self.build(
            plan=plan,
            references=references,
        )

        if placement_plan.is_valid:
            return placement_plan

        descriptions = "\n".join(
            (
                f"- [{issue.code}] "
                f"{issue.target}: "
                f"{issue.message}"
            )
            for issue in placement_plan.issues
            if issue.severity == "error"
        )

        raise ValueError(
            "El plan de colocación no es válido:\n"
            f"{descriptions}"
        )

    def _resolve_components(
        self,
        plan: MechanicalPlan,
        references: GeometricReferenceSystem,
        issues: list[PlacementIssue],
    ) -> list[PlacedComponent]:
        components: list[PlacedComponent] = []

        known_targets: set[str] = set()

        for placement in plan.component_placements:
            if placement.target in known_targets:
                issues.append(
                    PlacementIssue(
                        code="duplicate_target",
                        target=placement.target,
                        message=(
                            "Existe más de una colocación con el mismo "
                            "identificador de componente."
                        ),
                    )
                )
                continue

            known_targets.add(placement.target)

            if placement.dimensions is None:
                issues.append(
                    PlacementIssue(
                        code="missing_dimensions",
                        target=placement.target,
                        message=(
                            "El componente no contiene dimensiones físicas."
                        ),
                    )
                )
                continue

            try:
                dimensions = self._resolve_rotated_dimensions(
                    dimensions=placement.dimensions,
                    rotation_z_deg=placement.rotation_z_deg,
                )
            except ValueError as error:
                issues.append(
                    PlacementIssue(
                        code="unsupported_rotation",
                        target=placement.target,
                        message=str(error),
                    )
                )
                continue

            resolved = references.resolve_placement(placement)

            occupied_volume = self._build_component_volume(
                position=resolved.position,
                dimensions=dimensions,
                clearance_mm=placement.clearance_mm,
            )

            component = PlacedComponent(
                target=placement.target,
                source=placement,
                resolved=resolved,
                occupied_volume=occupied_volume,
                dimensions=dimensions,
            )

            components.append(component)

            if not self._volume_contains_volume(
                container=references.usable_interior,
                content=occupied_volume,
            ):
                issues.append(
                    PlacementIssue(
                        code="outside_usable_interior",
                        target=placement.target,
                        message=(
                            "El volumen ocupado por el componente excede "
                            "los límites del interior útil."
                        ),
                    )
                )

        return components

    def _resolve_reserved_zones(
        self,
        plan: MechanicalPlan,
        references: GeometricReferenceSystem,
        issues: list[PlacementIssue],
    ) -> list[ResolvedReservedZone]:
        resolved_zones: list[ResolvedReservedZone] = []

        known_names: set[str] = set()

        for zone in plan.reserved_zones:
            if zone.name in known_names:
                issues.append(
                    PlacementIssue(
                        code="duplicate_reserved_zone",
                        target=zone.name,
                        message=(
                            "Existe más de una zona reservada "
                            "con el mismo nombre."
                        ),
                    )
                )
                continue

            known_names.add(zone.name)

            resolved_zone = self._resolve_reserved_zone(
                zone=zone,
                references=references,
            )

            resolved_zones.append(resolved_zone)

            if not self._volume_contains_volume(
                container=references.usable_interior,
                content=resolved_zone.occupied_volume,
            ):
                issues.append(
                    PlacementIssue(
                        code="reserved_zone_outside_interior",
                        target=zone.name,
                        message=(
                            "La zona reservada excede los límites "
                            "del interior útil."
                        ),
                    )
                )

        return resolved_zones

    def _resolve_reserved_zone(
        self,
        zone: ReservedZone,
        references: GeometricReferenceSystem,
    ) -> ResolvedReservedZone:
        anchor = references.get_anchor(zone.anchor)

        center = Point3D(
            x_mm=anchor.x_mm + zone.offset.x_mm,
            y_mm=anchor.y_mm + zone.offset.y_mm,
            z_mm=anchor.z_mm + zone.offset.z_mm,
        )

        occupied_volume = self._build_centered_volume(
            center=center,
            dimensions=zone.dimensions,
        )

        return ResolvedReservedZone(
            name=zone.name,
            reason=zone.reason,
            occupied_volume=occupied_volume,
        )

    def _check_component_collisions(
        self,
        components: list[PlacedComponent],
        issues: list[PlacementIssue],
    ) -> None:
        for first_index, first in enumerate(components):
            if first.source.allow_overlap:
                continue

            for second in components[first_index + 1:]:
                if second.source.allow_overlap:
                    continue

                if self._volumes_intersect(
                    first.occupied_volume,
                    second.occupied_volume,
                ):
                    issues.append(
                        PlacementIssue(
                            code="component_collision",
                            target=first.target,
                            message=(
                                f"Colisiona con el componente "
                                f"'{second.target}'."
                            ),
                        )
                    )

    def _check_reserved_zone_collisions(
        self,
        components: list[PlacedComponent],
        reserved_zones: list[ResolvedReservedZone],
        issues: list[PlacementIssue],
    ) -> None:
        for component in components:
            if component.source.allow_overlap:
                continue

            for zone in reserved_zones:
                if self._volumes_intersect(
                    component.occupied_volume,
                    zone.occupied_volume,
                ):
                    issues.append(
                        PlacementIssue(
                            code="reserved_zone_collision",
                            target=component.target,
                            message=(
                                f"Invade la zona reservada "
                                f"'{zone.name}': {zone.reason}"
                            ),
                        )
                    )

    def _resolve_rotated_dimensions(
        self,
        dimensions: ComponentDimensions,
        rotation_z_deg: float,
    ) -> ComponentDimensions:
        normalized_rotation = rotation_z_deg % 360.0

        matched_rotation = self._match_orthogonal_rotation(
            normalized_rotation
        )

        if matched_rotation is None:
            raise ValueError(
                "Solo se admiten rotaciones ortogonales en Z: "
                "0, 90, 180 o 270 grados."
            )

        if matched_rotation in (90.0, 270.0):
            return ComponentDimensions(
                width_mm=dimensions.depth_mm,
                depth_mm=dimensions.width_mm,
                height_mm=dimensions.height_mm,
            )

        return dimensions

    def _match_orthogonal_rotation(
        self,
        rotation_z_deg: float,
    ) -> float | None:
        for allowed_rotation in self.ORTHOGONAL_ROTATIONS:
            if isclose(
                rotation_z_deg,
                allowed_rotation,
                abs_tol=1e-6,
            ):
                return allowed_rotation

        return None

    @staticmethod
    def _build_component_volume(
        position: Point3D,
        dimensions: ComponentDimensions,
        clearance_mm: float,
    ) -> AxisAlignedVolume:
        """
        Interpreta la posición del componente como centro en X/Y y
        superficie inferior en Z.

        Esta convención encaja con componentes apoyados sobre el suelo,
        soportes o superficies internas.
        """

        half_width = dimensions.width_mm / 2.0
        half_depth = dimensions.depth_mm / 2.0

        return AxisAlignedVolume(
            min_x_mm=(
                position.x_mm
                - half_width
                - clearance_mm
            ),
            max_x_mm=(
                position.x_mm
                + half_width
                + clearance_mm
            ),
            min_y_mm=(
                position.y_mm
                - half_depth
                - clearance_mm
            ),
            max_y_mm=(
                position.y_mm
                + half_depth
                + clearance_mm
            ),
            min_z_mm=(
                position.z_mm
                - clearance_mm
            ),
            max_z_mm=(
                position.z_mm
                + dimensions.height_mm
                + clearance_mm
            ),
        )

    @staticmethod
    def _build_centered_volume(
        center: Point3D,
        dimensions: ComponentDimensions,
    ) -> AxisAlignedVolume:
        half_width = dimensions.width_mm / 2.0
        half_depth = dimensions.depth_mm / 2.0
        half_height = dimensions.height_mm / 2.0

        return AxisAlignedVolume(
            min_x_mm=center.x_mm - half_width,
            max_x_mm=center.x_mm + half_width,
            min_y_mm=center.y_mm - half_depth,
            max_y_mm=center.y_mm + half_depth,
            min_z_mm=center.z_mm - half_height,
            max_z_mm=center.z_mm + half_height,
        )

    @staticmethod
    def _volume_contains_volume(
        container: AxisAlignedVolume,
        content: AxisAlignedVolume,
    ) -> bool:
        return (
            container.min_x_mm <= content.min_x_mm
            and content.max_x_mm <= container.max_x_mm
            and container.min_y_mm <= content.min_y_mm
            and content.max_y_mm <= container.max_y_mm
            and container.min_z_mm <= content.min_z_mm
            and content.max_z_mm <= container.max_z_mm
        )

    @staticmethod
    def _volumes_intersect(
        first: AxisAlignedVolume,
        second: AxisAlignedVolume,
    ) -> bool:
        """
        Considera colisión únicamente cuando existe solapamiento volumétrico.

        Dos volúmenes que solo se tocan en una cara o arista no se
        consideran colisionados.
        """

        return (
            first.min_x_mm < second.max_x_mm
            and first.max_x_mm > second.min_x_mm
            and first.min_y_mm < second.max_y_mm
            and first.max_y_mm > second.min_y_mm
            and first.min_z_mm < second.max_z_mm
            and first.max_z_mm > second.min_z_mm
        )