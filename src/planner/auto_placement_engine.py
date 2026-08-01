
from __future__ import annotations

from dataclasses import dataclass
from src.cad.geometric_reference_system import (
    AxisAlignedVolume,
    GeometricReferenceSystem,
)
from src.models.mechanical_plan import (
    ComponentDimensions,
    ComponentPlacement,
    MechanicalPlan,
    Offset3D,
)


@dataclass(frozen=True)
class AutoPlacementItem:
    """
    Componente pendiente de colocación automática.

    No contiene coordenadas absolutas. Solo describe:

    - identidad;
    - dimensiones;
    - holgura necesaria;
    - elevación sobre el suelo;
    - rotaciones permitidas.
    """

    target: str
    dimensions: ComponentDimensions

    clearance_mm: float = 1.0
    elevation_mm: float = 0.0

    allow_rotation: bool = True
    preferred_rotation_z_deg: float | None = None


@dataclass(frozen=True)
class AutoPlacementIssue:
    """
    Problema detectado durante la colocación automática.
    """

    code: str
    target: str
    message: str


@dataclass(frozen=True)
class AutoPlacedItem:
    """
    Componente colocado automáticamente.
    """

    item: AutoPlacementItem
    placement: ComponentPlacement
    occupied_volume: AxisAlignedVolume


@dataclass(frozen=True)
class AutoPlacementResult:
    """
    Resultado completo del AutoPlacementEngine.
    """

    placements: list[ComponentPlacement]
    placed_items: list[AutoPlacedItem]
    issues: list[AutoPlacementIssue]

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0


@dataclass(frozen=True)
class _PlacementCandidate:
    """
    Posición candidata evaluada internamente.
    """

    rotation_z_deg: float
    rotated_dimensions: ComponentDimensions

    center_x_mm: float
    center_y_mm: float

    occupied_volume: AxisAlignedVolume


class AutoPlacementEngine:
    """
    Motor básico de colocación automática.

    Estrategia de colocación:

    1. Ordenar componentes por superficie descendente.
    2. Generar posiciones candidatas junto a los límites disponibles.
    3. Probar orientación de 0° y 90°.
    4. Descartar posiciones fuera del interior útil.
    5. Descartar colisiones tridimensionales.
    6. Puntuar las soluciones por compacidad y posición.
    7. Producir ComponentPlacement compatibles con PlacementPlanner.

    Esta versión compara varias alternativas locales para obtener una
    distribución más compacta y robusta que el recorrido simple por filas.
    """

    DEFAULT_COMPONENT_GAP_MM = 2.0
    FLOAT_TOLERANCE_MM = 0.000001

    def place(
        self,
        plan: MechanicalPlan,
        items: list[AutoPlacementItem],
        *,
        references: GeometricReferenceSystem | None = None,
    ) -> AutoPlacementResult:
        reference_system = (
            references
            if references is not None
            else GeometricReferenceSystem(plan)
        )

        usable = reference_system.usable_interior
        issues = self._validate_items(items)

        if issues:
            return AutoPlacementResult(
                placements=[],
                placed_items=[],
                issues=issues,
            )

        ordered_items = sorted(
            items,
            key=self._surface_area_with_clearance,
            reverse=True,
        )

        placements: list[ComponentPlacement] = []
        placed_items: list[AutoPlacedItem] = []
        occupied_volumes: list[AxisAlignedVolume] = []

        for item in ordered_items:
            candidate = self._find_best_candidate(
                item=item,
                usable=usable,
                occupied_volumes=occupied_volumes,
            )

            if candidate is None:
                issues.append(
                    AutoPlacementIssue(
                        code="component_cannot_be_placed",
                        target=item.target,
                        message=(
                            "No existe espacio suficiente para colocar "
                            "el componente dentro del volumen interior útil."
                        ),
                    )
                )
                continue

            placement = self._candidate_to_placement(
                item=item,
                candidate=candidate,
                references=reference_system,
            )

            placements.append(placement)
            placed_items.append(
                AutoPlacedItem(
                    item=item,
                    placement=placement,
                    occupied_volume=candidate.occupied_volume,
                )
            )
            occupied_volumes.append(candidate.occupied_volume)

        return AutoPlacementResult(
            placements=placements,
            placed_items=placed_items,
            issues=issues,
        )

    def require_valid(

        self,
        plan: MechanicalPlan,
        items: list[AutoPlacementItem],
        *,
        references: GeometricReferenceSystem | None = None,
    ) -> AutoPlacementResult:
        """
        Ejecuta la colocación y lanza ValueError si no es válida.
        """

        result = self.place(
            plan=plan,
            items=items,
            references=references,
        )

        if result.is_valid:
            return result

        descriptions = "\n".join(
            (
                f"- [{issue.code}] "
                f"{issue.target}: "
                f"{issue.message}"
            )
            for issue in result.issues
        )

        raise ValueError(
            "La colocación automática no es válida:\n"
            f"{descriptions}"
        )

    def _find_best_candidate(
        self,
        *,
        item: AutoPlacementItem,
        usable: AxisAlignedVolume,
        occupied_volumes: list[AxisAlignedVolume],
    ) -> _PlacementCandidate | None:
        """
        Genera y compara todas las posiciones candidatas locales.
        """

        candidates: list[_PlacementCandidate] = []

        for start_x_mm, start_y_mm in self._candidate_start_positions(
            usable=usable,
            occupied_volumes=occupied_volumes,
        ):
            for rotation_z_deg in self._rotation_options(item):
                candidate = self._build_candidate(
                    item=item,
                    usable=usable,
                    occupied_volumes=occupied_volumes,
                    start_x_mm=start_x_mm,
                    start_y_mm=start_y_mm,
                    rotation_z_deg=rotation_z_deg,
                )

                if candidate is not None:
                    candidates.append(candidate)

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda candidate: self._candidate_score(
                candidate=candidate,
                usable=usable,
                occupied_volumes=occupied_volumes,
                item=item,
            ),
        )

    def _build_candidate(
        self,
        *,
        item: AutoPlacementItem,
        usable: AxisAlignedVolume,
        occupied_volumes: list[AxisAlignedVolume],
        start_x_mm: float,
        start_y_mm: float,
        rotation_z_deg: float,
    ) -> _PlacementCandidate | None:
        dimensions = self._rotated_dimensions(
            dimensions=item.dimensions,
            rotation_z_deg=rotation_z_deg,
        )

        total_width_mm = (
            dimensions.width_mm
            + 2.0 * item.clearance_mm
        )
        total_depth_mm = (
            dimensions.depth_mm
            + 2.0 * item.clearance_mm
        )

        center_x_mm = start_x_mm + total_width_mm / 2.0
        center_y_mm = start_y_mm + total_depth_mm / 2.0

        component_origin_z_mm = (
            usable.min_z_mm
            + item.elevation_mm
            + item.clearance_mm
        )

        occupied_volume = AxisAlignedVolume(
            min_x_mm=start_x_mm,
            max_x_mm=start_x_mm + total_width_mm,
            min_y_mm=start_y_mm,
            max_y_mm=start_y_mm + total_depth_mm,
            min_z_mm=(
                component_origin_z_mm
                - item.clearance_mm
            ),
            max_z_mm=(
                component_origin_z_mm
                + dimensions.height_mm
                + item.clearance_mm
            ),
        )

        if not self._volume_contains_volume(
            container=usable,
            content=occupied_volume,
        ):
            return None

        if self._collides_with_any(
            candidate=occupied_volume,
            occupied_volumes=occupied_volumes,
        ):
            return None

        return _PlacementCandidate(
            rotation_z_deg=rotation_z_deg,
            rotated_dimensions=dimensions,
            center_x_mm=center_x_mm,
            center_y_mm=center_y_mm,
            occupied_volume=occupied_volume,
        )

    def _candidate_start_positions(
        self,
        *,
        usable: AxisAlignedVolume,
        occupied_volumes: list[AxisAlignedVolume],
    ) -> list[tuple[float, float]]:
        """
        Crea esquinas candidatas a partir de los límites del interior y
        de los bordes derechos y superiores de los componentes colocados.
        """

        x_positions = {usable.min_x_mm}
        y_positions = {usable.min_y_mm}

        for occupied in occupied_volumes:
            x_positions.add(
                occupied.max_x_mm
                + self.DEFAULT_COMPONENT_GAP_MM
            )
            y_positions.add(
                occupied.max_y_mm
                + self.DEFAULT_COMPONENT_GAP_MM
            )

        positions = {
            (x_mm, y_mm)
            for x_mm in x_positions
            for y_mm in y_positions
            if x_mm <= usable.max_x_mm
            and y_mm <= usable.max_y_mm
        }

        return sorted(
            positions,
            key=lambda position: (position[1], position[0]),
        )

    def _candidate_score(
        self,
        *,
        candidate: _PlacementCandidate,
        usable: AxisAlignedVolume,
        occupied_volumes: list[AxisAlignedVolume],
        item: AutoPlacementItem,
    ) -> tuple[float, float, float, float]:
        """
        Menor puntuación significa una distribución más compacta.
        """

        volumes = [
            *occupied_volumes,
            candidate.occupied_volume,
        ]

        used_max_x_mm = max(
            volume.max_x_mm
            for volume in volumes
        )
        used_max_y_mm = max(
            volume.max_y_mm
            for volume in volumes
        )

        used_width_mm = used_max_x_mm - usable.min_x_mm
        used_depth_mm = used_max_y_mm - usable.min_y_mm
        bounding_area_mm2 = used_width_mm * used_depth_mm

        preferred_rotation_penalty = 0.0
        if item.preferred_rotation_z_deg is not None:
            preferred = item.preferred_rotation_z_deg % 360.0
            if candidate.rotation_z_deg != preferred:
                preferred_rotation_penalty = 1.0

        return (
            bounding_area_mm2,
            used_max_y_mm,
            used_max_x_mm,
            preferred_rotation_penalty,
        )

    def _candidate_to_placement(

        self,
        *,
        item: AutoPlacementItem,
        candidate: _PlacementCandidate,
        references: GeometricReferenceSystem,
    ) -> ComponentPlacement:
        """
        Convierte una posición cartesiana en un ComponentPlacement
        relativo al anclaje floor_center.
        """

        floor_center = references.get_anchor(
            "floor_center"
        )

        return ComponentPlacement(
            target=item.target,
            anchor="floor_center",
            offset=Offset3D(
                x_mm=(
                    candidate.center_x_mm
                    - floor_center.x_mm
                ),
                y_mm=(
                    candidate.center_y_mm
                    - floor_center.y_mm
                ),
                z_mm=(
                    item.elevation_mm
                    + item.clearance_mm
                ),
            ),
            dimensions=item.dimensions,
            rotation_z_deg=candidate.rotation_z_deg,
            clearance_mm=item.clearance_mm,
        )

    def _validate_items(
        self,
        items: list[AutoPlacementItem],
    ) -> list[AutoPlacementIssue]:
        issues: list[AutoPlacementIssue] = []

        seen_targets: set[str] = set()

        for item in items:
            if not item.target.strip():
                issues.append(
                    AutoPlacementIssue(
                        code="empty_target",
                        target=item.target,
                        message=(
                            "El componente no tiene un identificador válido."
                        ),
                    )
                )

            if item.target in seen_targets:
                issues.append(
                    AutoPlacementIssue(
                        code="duplicate_target",
                        target=item.target,
                        message=(
                            "Existe más de un componente con el mismo target."
                        ),
                    )
                )

            seen_targets.add(item.target)

            if item.dimensions.width_mm <= 0:
                issues.append(
                    AutoPlacementIssue(
                        code="invalid_width",
                        target=item.target,
                        message=(
                            "La anchura del componente debe ser mayor que cero."
                        ),
                    )
                )

            if item.dimensions.depth_mm <= 0:
                issues.append(
                    AutoPlacementIssue(
                        code="invalid_depth",
                        target=item.target,
                        message=(
                            "La profundidad del componente debe ser mayor que cero."
                        ),
                    )
                )

            if item.dimensions.height_mm <= 0:
                issues.append(
                    AutoPlacementIssue(
                        code="invalid_height",
                        target=item.target,
                        message=(
                            "La altura del componente debe ser mayor que cero."
                        ),
                    )
                )

            if item.clearance_mm < 0:
                issues.append(
                    AutoPlacementIssue(
                        code="invalid_clearance",
                        target=item.target,
                        message=(
                            "La holgura no puede ser negativa."
                        ),
                    )
                )

            if item.elevation_mm < 0:
                issues.append(
                    AutoPlacementIssue(
                        code="invalid_elevation",
                        target=item.target,
                        message=(
                            "La elevación sobre el suelo no puede ser negativa."
                        ),
                    )
                )

        return issues

    @staticmethod
    def _surface_area_with_clearance(
        item: AutoPlacementItem,
    ) -> float:
        return (
            item.dimensions.width_mm
            + 2.0 * item.clearance_mm
        ) * (
            item.dimensions.depth_mm
            + 2.0 * item.clearance_mm
        )

    @staticmethod
    def _rotation_options(
        item: AutoPlacementItem,
    ) -> list[float]:
        """
        Devuelve las orientaciones que deben probarse.
        """

        if item.preferred_rotation_z_deg is not None:
            preferred = (
                item.preferred_rotation_z_deg
                % 360.0
            )

            if not item.allow_rotation:
                return [preferred]

            alternative = (
                preferred + 90.0
            ) % 360.0

            return [
                preferred,
                alternative,
            ]

        if item.allow_rotation:
            return [
                0.0,
                90.0,
            ]

        return [0.0]

    @staticmethod
    def _rotated_dimensions(
        *,
        dimensions: ComponentDimensions,
        rotation_z_deg: float,
    ) -> ComponentDimensions:
        """
        Intercambia anchura y profundidad para giros de 90° y 270°.
        """

        normalized = rotation_z_deg % 360.0

        if normalized in (
            90.0,
            270.0,
        ):
            return ComponentDimensions(
                width_mm=dimensions.depth_mm,
                depth_mm=dimensions.width_mm,
                height_mm=dimensions.height_mm,
            )

        return dimensions

    @staticmethod
    def _volume_contains_volume(
        *,
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

    def _collides_with_any(
        self,
        *,
        candidate: AxisAlignedVolume,
        occupied_volumes: list[AxisAlignedVolume],
    ) -> bool:
        return any(
            self._volumes_intersect(
                candidate,
                occupied,
            )
            for occupied in occupied_volumes
        )

    @staticmethod
    def _volumes_intersect(
        first: AxisAlignedVolume,
        second: AxisAlignedVolume,
    ) -> bool:
        """
        El contacto exacto entre caras no se considera colisión.
        """

        return (
            first.min_x_mm < second.max_x_mm
            and first.max_x_mm > second.min_x_mm
            and first.min_y_mm < second.max_y_mm
            and first.max_y_mm > second.min_y_mm
            and first.min_z_mm < second.max_z_mm
            and first.max_z_mm > second.min_z_mm
        )