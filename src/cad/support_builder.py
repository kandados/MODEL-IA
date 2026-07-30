from __future__ import annotations

from dataclasses import dataclass

import cadquery as cq

from src.cad.geometric_reference_system import (
    GeometricReferenceSystem,
)
from src.models.mechanical_plan import (
    MechanicalPlan,
    Support,
)
from src.planner.placement_planner import (
    PlacedComponent,
    PlacementPlan,
    PlacementPlanner,
)


@dataclass(frozen=True)
class SupportPosition:
    """
    Posición cartesiana de un elemento individual de soporte.
    """

    x_mm: float
    y_mm: float


class SupportBuilder:
    """
    Genera soportes internos desde un PlacementPlan.

    Responsabilidades:

    - localizar el componente objetivo;
    - consumir su posición y dimensiones resueltas;
    - generar la geometría del soporte.

    Esta clase no decide la posición general de ningún componente.
    """

    DEFAULT_STANDOFF_DIAMETER_MM = 6.0
    DEFAULT_HOLE_DIAMETER_MM = 2.8
    DEFAULT_STANDOFF_EDGE_INSET_MM = 4.0

    DEFAULT_BATTERY_WALL_MM = 1.5
    DEFAULT_BATTERY_FLOOR_MM = 1.2
    DEFAULT_BATTERY_HOLDER_HEIGHT_MM = 6.0

    DEFAULT_DISPLAY_FRAME_MM = 2.0
    DEFAULT_DISPLAY_FRAME_HEIGHT_MM = 3.0

    DEFAULT_GENERIC_HEIGHT_MM = 3.0
    DEFAULT_GENERIC_FOOTPRINT_RATIO = 0.25
    DEFAULT_GENERIC_MINIMUM_SIZE_MM = 4.0
    DEFAULT_GENERIC_MAXIMUM_SIZE_MM = 20.0

    BOOLEAN_TOLERANCE_MM = 0.10
    MINIMUM_SUPPORT_HEIGHT_MM = 0.20

    def build(
        self,
        plan: MechanicalPlan,
        *,
        references: GeometricReferenceSystem | None = None,
        placement_plan: PlacementPlan | None = None,
    ) -> cq.Workplane:
        """
        Construye todos los soportes declarados en MechanicalPlan.

        El plan de colocación puede proporcionarse desde el pipeline para
        evitar recalcularlo. Si no se proporciona, se genera y valida aquí.
        """

        reference_system = (
            references
            if references is not None
            else GeometricReferenceSystem(plan)
        )

        resolved_plan = (
            placement_plan
            if placement_plan is not None
            else PlacementPlanner().require_valid(
                plan=plan,
                references=reference_system,
            )
        )

        components_by_target = {
            component.target: component
            for component in resolved_plan.components
        }

        supports = cq.Workplane("XY")

        for support in plan.supports:
            component = components_by_target.get(support.target)

            if component is None:
                raise ValueError(
                    "No puede generarse el soporte "
                    f"'{support.kind}' para '{support.target}': "
                    "no existe una colocación válida con ese target."
                )

            support_body = self._build_support(
                support=support,
                component=component,
                references=reference_system,
            )

            supports = supports.union(support_body)

        return supports

    def _build_support(
        self,
        support: Support,
        component: PlacedComponent,
        references: GeometricReferenceSystem,
    ) -> cq.Workplane:
        if support.kind == "pcb_standoff":
            return self._build_pcb_standoffs(
                component=component,
                quantity=support.quantity,
                references=references,
            )

        if support.kind == "battery_holder":
            return self._build_battery_holder(
                component=component,
                references=references,
            )

        if support.kind == "display_frame":
            return self._build_display_frame(
                component=component,
                references=references,
            )

        return self._build_generic_support(
            component=component,
            references=references,
        )

    def _build_pcb_standoffs(
        self,
        component: PlacedComponent,
        quantity: int,
        references: GeometricReferenceSystem,
    ) -> cq.Workplane:
        """
        Genera separadores dentro de la huella de la PCB.

        La altura se calcula desde el suelo físico hasta la superficie
        inferior declarada para la placa.
        """

        floor_z = references.physical_interior.min_z_mm

        support_height = (
            component.resolved.position.z_mm
            - floor_z
        )

        if support_height < self.MINIMUM_SUPPORT_HEIGHT_MM:
            raise ValueError(
                f"La PCB '{component.target}' no dispone de altura "
                "suficiente sobre el suelo para generar separadores. "
                f"Altura disponible: {support_height:.3f} mm."
            )

        positions = self._calculate_standoff_positions(
            component=component,
            quantity=quantity,
        )

        result = cq.Workplane("XY")

        for position in positions:
            standoff = self._build_single_standoff(
                x_mm=position.x_mm,
                y_mm=position.y_mm,
                floor_z_mm=floor_z,
                height_mm=support_height,
            )

            result = result.union(standoff)

        return result

    def _calculate_standoff_positions(
        self,
        component: PlacedComponent,
        quantity: int,
    ) -> list[SupportPosition]:
        """
        Distribuye los separadores respecto a la huella real del componente.

        Para uno, dos, tres o cuatro soportes se utilizan configuraciones
        simétricas. Para cantidades superiores se genera una cuadrícula
        contenida dentro de la huella.
        """

        quantity = max(1, quantity)

        center_x = component.resolved.position.x_mm
        center_y = component.resolved.position.y_mm

        half_width = component.dimensions.width_mm / 2.0
        half_depth = component.dimensions.depth_mm / 2.0

        inset_x = min(
            self.DEFAULT_STANDOFF_EDGE_INSET_MM,
            half_width * 0.50,
        )

        inset_y = min(
            self.DEFAULT_STANDOFF_EDGE_INSET_MM,
            half_depth * 0.50,
        )

        left_x = center_x - half_width + inset_x
        right_x = center_x + half_width - inset_x

        front_y = center_y - half_depth + inset_y
        rear_y = center_y + half_depth - inset_y

        if quantity == 1:
            return [
                SupportPosition(
                    x_mm=center_x,
                    y_mm=center_y,
                )
            ]

        if quantity == 2:
            return [
                SupportPosition(
                    x_mm=left_x,
                    y_mm=center_y,
                ),
                SupportPosition(
                    x_mm=right_x,
                    y_mm=center_y,
                ),
            ]

        if quantity == 3:
            return [
                SupportPosition(
                    x_mm=left_x,
                    y_mm=front_y,
                ),
                SupportPosition(
                    x_mm=right_x,
                    y_mm=front_y,
                ),
                SupportPosition(
                    x_mm=center_x,
                    y_mm=rear_y,
                ),
            ]

        if quantity == 4:
            return [
                SupportPosition(
                    x_mm=left_x,
                    y_mm=front_y,
                ),
                SupportPosition(
                    x_mm=right_x,
                    y_mm=front_y,
                ),
                SupportPosition(
                    x_mm=left_x,
                    y_mm=rear_y,
                ),
                SupportPosition(
                    x_mm=right_x,
                    y_mm=rear_y,
                ),
            ]

        return self._build_support_grid(
            quantity=quantity,
            min_x_mm=left_x,
            max_x_mm=right_x,
            min_y_mm=front_y,
            max_y_mm=rear_y,
        )

    def _build_support_grid(
        self,
        *,
        quantity: int,
        min_x_mm: float,
        max_x_mm: float,
        min_y_mm: float,
        max_y_mm: float,
    ) -> list[SupportPosition]:
        """
        Genera una cuadrícula aproximadamente cuadrada para cantidades
        superiores a cuatro.
        """

        columns = 1

        while columns * columns < quantity:
            columns += 1

        rows = (
            quantity
            + columns
            - 1
        ) // columns

        x_positions = self._evenly_spaced_values(
            minimum=min_x_mm,
            maximum=max_x_mm,
            count=columns,
        )

        y_positions = self._evenly_spaced_values(
            minimum=min_y_mm,
            maximum=max_y_mm,
            count=rows,
        )

        positions: list[SupportPosition] = []

        for y_mm in y_positions:
            for x_mm in x_positions:
                positions.append(
                    SupportPosition(
                        x_mm=x_mm,
                        y_mm=y_mm,
                    )
                )

                if len(positions) == quantity:
                    return positions

        return positions

    def _build_single_standoff(
        self,
        *,
        x_mm: float,
        y_mm: float,
        floor_z_mm: float,
        height_mm: float,
    ) -> cq.Workplane:
        outer = (
            cq.Workplane("XY")
            .circle(
                self.DEFAULT_STANDOFF_DIAMETER_MM
                / 2.0
            )
            .extrude(height_mm)
            .translate(
                (
                    x_mm,
                    y_mm,
                    floor_z_mm,
                )
            )
        )

        hole = (
            cq.Workplane("XY")
            .circle(
                self.DEFAULT_HOLE_DIAMETER_MM
                / 2.0
            )
            .extrude(
                height_mm
                + 2.0 * self.BOOLEAN_TOLERANCE_MM
            )
            .translate(
                (
                    x_mm,
                    y_mm,
                    floor_z_mm
                    - self.BOOLEAN_TOLERANCE_MM,
                )
            )
        )

        return outer.cut(hole)

    def _build_battery_holder(
        self,
        component: PlacedComponent,
        references: GeometricReferenceSystem,
    ) -> cq.Workplane:
        """
        Genera una bandeja usando las dimensiones reales de la batería.
        """

        center_x = component.resolved.position.x_mm
        center_y = component.resolved.position.y_mm
        floor_z = references.physical_interior.min_z_mm

        wall = self.DEFAULT_BATTERY_WALL_MM
        floor = self.DEFAULT_BATTERY_FLOOR_MM

        outer_width = (
            component.dimensions.width_mm
            + 2.0 * wall
        )

        outer_depth = (
            component.dimensions.depth_mm
            + 2.0 * wall
        )

        holder_height = min(
            self.DEFAULT_BATTERY_HOLDER_HEIGHT_MM,
            component.dimensions.height_mm,
        )

        if holder_height <= floor:
            holder_height = floor + self.MINIMUM_SUPPORT_HEIGHT_MM

        outer = (
            cq.Workplane("XY")
            .box(
                outer_width,
                outer_depth,
                holder_height,
                centered=(True, True, False),
            )
            .translate(
                (
                    center_x,
                    center_y,
                    floor_z,
                )
            )
        )

        inner = (
            cq.Workplane("XY")
            .box(
                component.dimensions.width_mm,
                component.dimensions.depth_mm,
                holder_height,
                centered=(True, True, False),
            )
            .translate(
                (
                    center_x,
                    center_y,
                    floor_z + floor,
                )
            )
        )

        return outer.cut(inner)

    def _build_display_frame(
        self,
        component: PlacedComponent,
        references: GeometricReferenceSystem,
    ) -> cq.Workplane:
        """
        Genera un marco a partir de las dimensiones reales de la pantalla.
        """

        center_x = component.resolved.position.x_mm
        center_y = component.resolved.position.y_mm
        floor_z = references.physical_interior.min_z_mm

        frame = self.DEFAULT_DISPLAY_FRAME_MM
        height = self.DEFAULT_DISPLAY_FRAME_HEIGHT_MM

        outer_width = (
            component.dimensions.width_mm
            + 2.0 * frame
        )

        outer_depth = (
            component.dimensions.depth_mm
            + 2.0 * frame
        )

        outer = (
            cq.Workplane("XY")
            .box(
                outer_width,
                outer_depth,
                height,
                centered=(True, True, False),
            )
            .translate(
                (
                    center_x,
                    center_y,
                    floor_z,
                )
            )
        )

        inner = (
            cq.Workplane("XY")
            .box(
                component.dimensions.width_mm,
                component.dimensions.depth_mm,
                height
                + 2.0 * self.BOOLEAN_TOLERANCE_MM,
                centered=(True, True, False),
            )
            .translate(
                (
                    center_x,
                    center_y,
                    floor_z
                    - self.BOOLEAN_TOLERANCE_MM,
                )
            )
        )

        return outer.cut(inner)

    def _build_generic_support(
        self,
        component: PlacedComponent,
        references: GeometricReferenceSystem,
    ) -> cq.Workplane:
        """
        Genera un pedestal proporcional a la huella del componente.
        """

        center_x = component.resolved.position.x_mm
        center_y = component.resolved.position.y_mm
        floor_z = references.physical_interior.min_z_mm

        width = self._clamp(
            component.dimensions.width_mm
            * self.DEFAULT_GENERIC_FOOTPRINT_RATIO,
            minimum=self.DEFAULT_GENERIC_MINIMUM_SIZE_MM,
            maximum=self.DEFAULT_GENERIC_MAXIMUM_SIZE_MM,
        )

        depth = self._clamp(
            component.dimensions.depth_mm
            * self.DEFAULT_GENERIC_FOOTPRINT_RATIO,
            minimum=self.DEFAULT_GENERIC_MINIMUM_SIZE_MM,
            maximum=self.DEFAULT_GENERIC_MAXIMUM_SIZE_MM,
        )

        available_height = (
            component.resolved.position.z_mm
            - floor_z
        )

        height = (
            available_height
            if available_height >= self.MINIMUM_SUPPORT_HEIGHT_MM
            else self.DEFAULT_GENERIC_HEIGHT_MM
        )

        return (
            cq.Workplane("XY")
            .box(
                width,
                depth,
                height,
                centered=(True, True, False),
            )
            .translate(
                (
                    center_x,
                    center_y,
                    floor_z,
                )
            )
        )

    @staticmethod
    def _evenly_spaced_values(
        *,
        minimum: float,
        maximum: float,
        count: int,
    ) -> list[float]:
        if count <= 1:
            return [
                (minimum + maximum) / 2.0
            ]

        step = (
            maximum
            - minimum
        ) / (
            count
            - 1
        )

        return [
            minimum + index * step
            for index in range(count)
        ]

    @staticmethod
    def _clamp(
        value: float,
        *,
        minimum: float,
        maximum: float,
    ) -> float:
        return max(
            minimum,
            min(
                value,
                maximum,
            ),
        )