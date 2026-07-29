from __future__ import annotations

import re

import cadquery as cq

from src.cad.geometry_primitives import GeometryPrimitives
from src.models.mechanical_plan import MechanicalPlan


class EnclosureBuilder:
    """
    Genera una carcasa formada por una base hueca y una tapa independiente.

    La cavidad interior se crea mediante una operación booleana de corte.
    No se utiliza Workplane.shell(), ya que OpenCascade puede fallar al
    engrosar o vaciar sólidos redondeados.
    """

    DEFAULT_WALL_THICKNESS = 2.0
    DEFAULT_CORNER_RADIUS = 2.0
    BASE_HEIGHT_RATIO = 0.60

    BOOLEAN_TOLERANCE = 0.10

    def build(
        self,
        plan: MechanicalPlan,
    ) -> cq.Workplane:
        """
        Construye una carcasa hueca completa abierta por arriba.

        Este método se conserva como operación genérica. Para la exportación
        final deben utilizarse build_base() y build_lid().
        """

        box = self._get_bounding_box(plan)
        wall_thickness = self._resolve_wall_thickness(plan)

        self._validate_dimensions(
            width_mm=box.width_mm,
            depth_mm=box.depth_mm,
            height_mm=box.height_mm,
            wall_thickness_mm=wall_thickness,
        )

        return self._build_open_container(
            width_mm=box.width_mm,
            depth_mm=box.depth_mm,
            height_mm=box.height_mm,
            wall_thickness_mm=wall_thickness,
            corner_radius_mm=self.DEFAULT_CORNER_RADIUS,
        )

    def build_base(
        self,
        plan: MechanicalPlan,
    ) -> cq.Workplane:
        """
        Construye la parte inferior de la carcasa.

        La base dispone de:

        - suelo;
        - cuatro paredes;
        - abertura superior;
        - esquinas exteriores redondeadas.
        """

        box = self._get_bounding_box(plan)
        wall_thickness = self._resolve_wall_thickness(plan)

        self._validate_dimensions(
            width_mm=box.width_mm,
            depth_mm=box.depth_mm,
            height_mm=box.height_mm,
            wall_thickness_mm=wall_thickness,
        )

        base_height = (
            box.height_mm
            * self.BASE_HEIGHT_RATIO
        )

        if base_height <= wall_thickness:
            raise ValueError(
                "La altura calculada para la base no permite crear "
                "un suelo con el grosor solicitado."
            )

        return self._build_open_container(
            width_mm=box.width_mm,
            depth_mm=box.depth_mm,
            height_mm=base_height,
            wall_thickness_mm=wall_thickness,
            corner_radius_mm=self.DEFAULT_CORNER_RADIUS,
        )

    def build_lid(
        self,
        plan: MechanicalPlan,
    ) -> cq.Workplane:
        """
        Construye una tapa independiente.

        La tapa se genera apoyada sobre el plano XY para facilitar:

        - la visualización;
        - la validación;
        - la exportación;
        - la impresión 3D.

        Su cavidad se abre por la parte inferior, dejando una superficie
        superior cerrada.
        """

        box = self._get_bounding_box(plan)
        wall_thickness = self._resolve_wall_thickness(plan)

        self._validate_dimensions(
            width_mm=box.width_mm,
            depth_mm=box.depth_mm,
            height_mm=box.height_mm,
            wall_thickness_mm=wall_thickness,
        )

        lid_height = (
            box.height_mm
            * (
                1.0
                - self.BASE_HEIGHT_RATIO
            )
        )

        if lid_height <= wall_thickness:
            raise ValueError(
                "La altura calculada para la tapa no permite crear "
                "un techo con el grosor solicitado."
            )

        return self._build_downward_open_lid(
            width_mm=box.width_mm,
            depth_mm=box.depth_mm,
            height_mm=lid_height,
            wall_thickness_mm=wall_thickness,
            corner_radius_mm=self.DEFAULT_CORNER_RADIUS,
        )

    def _build_open_container(
        self,
        width_mm: float,
        depth_mm: float,
        height_mm: float,
        wall_thickness_mm: float,
        corner_radius_mm: float,
    ) -> cq.Workplane:
        """
        Construye un recipiente abierto por arriba mediante resta booleana.
        """

        outer_radius = self._calculate_safe_corner_radius(
            width_mm=width_mm,
            depth_mm=depth_mm,
            requested_radius_mm=corner_radius_mm,
        )

        outer = self._build_rounded_box(
            width_mm=width_mm,
            depth_mm=depth_mm,
            height_mm=height_mm,
            corner_radius_mm=outer_radius,
        )

        inner_width = (
            width_mm
            - 2.0 * wall_thickness_mm
        )

        inner_depth = (
            depth_mm
            - 2.0 * wall_thickness_mm
        )

        inner_height = (
            height_mm
            - wall_thickness_mm
            + self.BOOLEAN_TOLERANCE
        )

        inner_radius = self._calculate_inner_radius(
            outer_radius_mm=outer_radius,
            wall_thickness_mm=wall_thickness_mm,
            inner_width_mm=inner_width,
            inner_depth_mm=inner_depth,
        )

        inner = self._build_rounded_box(
            width_mm=inner_width,
            depth_mm=inner_depth,
            height_mm=inner_height,
            corner_radius_mm=inner_radius,
        )

        inner = inner.translate(
            (
                0.0,
                0.0,
                wall_thickness_mm,
            )
        )

        result = outer.cut(inner)

        self._validate_resulting_solid(
            result,
            operation_name="construcción de la base hueca",
        )

        return result

    def _build_downward_open_lid(
        self,
        width_mm: float,
        depth_mm: float,
        height_mm: float,
        wall_thickness_mm: float,
        corner_radius_mm: float,
    ) -> cq.Workplane:
        """
        Construye una tapa abierta por la cara inferior.

        La cavidad comienza ligeramente por debajo de Z=0 para garantizar
        que atraviese completamente la cara inferior durante el corte.
        """

        outer_radius = self._calculate_safe_corner_radius(
            width_mm=width_mm,
            depth_mm=depth_mm,
            requested_radius_mm=corner_radius_mm,
        )

        outer = self._build_rounded_box(
            width_mm=width_mm,
            depth_mm=depth_mm,
            height_mm=height_mm,
            corner_radius_mm=outer_radius,
        )

        inner_width = (
            width_mm
            - 2.0 * wall_thickness_mm
        )

        inner_depth = (
            depth_mm
            - 2.0 * wall_thickness_mm
        )

        inner_height = (
            height_mm
            - wall_thickness_mm
            + self.BOOLEAN_TOLERANCE
        )

        inner_radius = self._calculate_inner_radius(
            outer_radius_mm=outer_radius,
            wall_thickness_mm=wall_thickness_mm,
            inner_width_mm=inner_width,
            inner_depth_mm=inner_depth,
        )

        inner = self._build_rounded_box(
            width_mm=inner_width,
            depth_mm=inner_depth,
            height_mm=inner_height,
            corner_radius_mm=inner_radius,
        )

        inner = inner.translate(
            (
                0.0,
                0.0,
                -self.BOOLEAN_TOLERANCE,
            )
        )

        result = outer.cut(inner)

        self._validate_resulting_solid(
            result,
            operation_name="construcción de la tapa hueca",
        )

        return result

    def _build_rounded_box(
        self,
        width_mm: float,
        depth_mm: float,
        height_mm: float,
        corner_radius_mm: float,
    ) -> cq.Workplane:
        """
        Construye una caja y redondea únicamente las aristas verticales.

        El filete se aplica antes de cualquier resta booleana para mantener
        una topología sencilla y predecible.
        """

        body = GeometryPrimitives.box(
            width_mm=width_mm,
            depth_mm=depth_mm,
            height_mm=height_mm,
        )

        if corner_radius_mm <= 0:
            return body

        return GeometryPrimitives.fillet(
            body=body,
            radius_mm=corner_radius_mm,
            edge_selector="|Z",
        )

    def _resolve_wall_thickness(
        self,
        plan: MechanicalPlan,
    ) -> float:
        """
        Busca el grosor de pared dentro de las reglas del MechanicalPlan.
        """

        patterns = (
            r"wall_thickness\s*=\s*([0-9]+(?:[.,][0-9]+)?)",
            r"wall thickness\s*=\s*([0-9]+(?:[.,][0-9]+)?)",
            r"grosor(?:\s+de)?\s+pared(?:es)?\s*=\s*"
            r"([0-9]+(?:[.,][0-9]+)?)",
        )

        for rule in plan.validation_rules:
            normalized = rule.strip().lower()

            for pattern in patterns:
                match = re.search(
                    pattern,
                    normalized,
                )

                if match is None:
                    continue

                value_text = (
                    match
                    .group(1)
                    .replace(",", ".")
                )

                try:
                    value = float(value_text)
                except ValueError:
                    continue

                if value > 0:
                    return value

        return self.DEFAULT_WALL_THICKNESS

    @staticmethod
    def _get_bounding_box(
        plan: MechanicalPlan,
    ):
        if plan.external_bounding_box is None:
            raise ValueError(
                "MechanicalPlan no contiene dimensiones exteriores."
            )

        return plan.external_bounding_box

    @staticmethod
    def _calculate_safe_corner_radius(
        width_mm: float,
        depth_mm: float,
        requested_radius_mm: float,
    ) -> float:
        """
        Limita el radio exterior para evitar filetes degenerados.
        """

        shortest_side = min(
            width_mm,
            depth_mm,
        )

        maximum_radius = (
            shortest_side
            * 0.20
        )

        return max(
            0.0,
            min(
                requested_radius_mm,
                maximum_radius,
            ),
        )

    @staticmethod
    def _calculate_inner_radius(
        outer_radius_mm: float,
        wall_thickness_mm: float,
        inner_width_mm: float,
        inner_depth_mm: float,
    ) -> float:
        """
        Calcula el radio interior manteniendo un grosor aproximadamente
        uniforme en las esquinas.
        """

        desired_radius = max(
            0.0,
            outer_radius_mm
            - wall_thickness_mm,
        )

        maximum_radius = (
            min(
                inner_width_mm,
                inner_depth_mm,
            )
            * 0.20
        )

        return min(
            desired_radius,
            maximum_radius,
        )

    @staticmethod
    def _validate_dimensions(
        width_mm: float,
        depth_mm: float,
        height_mm: float,
        wall_thickness_mm: float,
    ) -> None:
        dimensions = {
            "width_mm": width_mm,
            "depth_mm": depth_mm,
            "height_mm": height_mm,
            "wall_thickness_mm": wall_thickness_mm,
        }

        for name, value in dimensions.items():
            if value <= 0:
                raise ValueError(
                    f"{name} debe ser mayor que cero. "
                    f"Valor recibido: {value}"
                )

        minimum_horizontal_dimension = (
            wall_thickness_mm
            * 2.0
        )

        if width_mm <= minimum_horizontal_dimension:
            raise ValueError(
                "El ancho exterior no permite aplicar el grosor "
                "de pared solicitado."
            )

        if depth_mm <= minimum_horizontal_dimension:
            raise ValueError(
                "La profundidad exterior no permite aplicar el grosor "
                "de pared solicitado."
            )

        if height_mm <= wall_thickness_mm:
            raise ValueError(
                "La altura exterior no permite aplicar el grosor "
                "de pared solicitado."
            )

    @staticmethod
    def _validate_resulting_solid(
        body: cq.Workplane,
        operation_name: str,
    ) -> None:
        """
        Comprueba que la operación booleana produjo un único sólido válido.
        """

        solid_count = body.solids().size()

        if solid_count != 1:
            raise ValueError(
                f"La {operation_name} produjo {solid_count} sólidos. "
                "Se esperaba exactamente uno."
            )

        shape = body.val()

        if shape is None:
            raise ValueError(
                f"La {operation_name} no produjo ninguna geometría."
            )

        if not shape.isValid():
            raise ValueError(
                f"La geometría resultante de la {operation_name} "
                "no es válida."
            )

        if shape.Volume() <= 0:
            raise ValueError(
                f"La geometría resultante de la {operation_name} "
                "no tiene volumen positivo."
            )