from __future__ import annotations

import cadquery as cq


class GeometryPrimitives:
    """Utilidades geométricas reutilizables basadas en CadQuery."""

    @staticmethod
    def box(
        width_mm: float,
        depth_mm: float,
        height_mm: float,
    ) -> cq.Workplane:
        GeometryPrimitives._validate_positive(
            width_mm=width_mm,
            depth_mm=depth_mm,
            height_mm=height_mm,
        )

        return (
            cq.Workplane("XY")
            .box(
                width_mm,
                depth_mm,
                height_mm,
                centered=(True, True, False),
            )
        )

    @staticmethod
    def cylinder(
        radius_mm: float,
        height_mm: float,
    ) -> cq.Workplane:
        GeometryPrimitives._validate_positive(
            radius_mm=radius_mm,
            height_mm=height_mm,
        )

        return (
            cq.Workplane("XY")
            .circle(radius_mm)
            .extrude(height_mm)
        )

    @staticmethod
    def hole(
        radius_mm: float,
        depth_mm: float,
    ) -> cq.Workplane:
        GeometryPrimitives._validate_positive(
            radius_mm=radius_mm,
            depth_mm=depth_mm,
        )

        return (
            cq.Workplane("XY")
            .circle(radius_mm)
            .cutBlind(-depth_mm)
        )

    @staticmethod
    def translate(
        body: cq.Workplane,
        x: float,
        y: float,
        z: float,
    ) -> cq.Workplane:
        return body.translate((x, y, z))

    @staticmethod
    def rotate(
        body: cq.Workplane,
        start: tuple[float, float, float],
        end: tuple[float, float, float],
        angle_deg: float,
    ) -> cq.Workplane:
        return body.rotate(
            start,
            end,
            angle_deg,
        )

    @staticmethod
    def union(
        a: cq.Workplane,
        b: cq.Workplane,
    ) -> cq.Workplane:
        return a.union(b)

    @staticmethod
    def cut(
        a: cq.Workplane,
        b: cq.Workplane,
    ) -> cq.Workplane:
        return a.cut(b)

    @staticmethod
    def intersect(
        a: cq.Workplane,
        b: cq.Workplane,
    ) -> cq.Workplane:
        return a.intersect(b)

    @staticmethod
    def shell(
        body: cq.Workplane,
        thickness_mm: float,
        opening_selector: str = ">Z",
    ) -> cq.Workplane:
        GeometryPrimitives._validate_positive(
            thickness_mm=thickness_mm,
        )

        selected_faces = body.faces(
            opening_selector
        )

        if selected_faces.size() == 0:
            raise ValueError(
                "No se encontró ninguna cara para crear la abertura "
                "de la carcasa."
            )

        return selected_faces.shell(
            -thickness_mm
        )

    @staticmethod
    def fillet(
        body: cq.Workplane,
        radius_mm: float,
        edge_selector: str = "|Z",
    ) -> cq.Workplane:
        """
        Redondea únicamente las aristas indicadas.

        Por defecto se seleccionan las aristas verticales. No se permite
        aplicar el redondeo indiscriminadamente a todas las aristas porque
        OpenCascade puede fallar con sólidos huecos o geometrías complejas.
        """

        GeometryPrimitives._validate_positive(
            radius_mm=radius_mm,
        )

        selected_edges = body.edges(
            edge_selector
        )

        if selected_edges.size() == 0:
            return body

        return selected_edges.fillet(
            radius_mm
        )

    @staticmethod
    def chamfer(
        body: cq.Workplane,
        distance_mm: float,
        edge_selector: str = "|Z",
    ) -> cq.Workplane:
        """
        Aplica un chaflán únicamente a las aristas seleccionadas.
        """

        GeometryPrimitives._validate_positive(
            distance_mm=distance_mm,
        )

        selected_edges = body.edges(
            edge_selector
        )

        if selected_edges.size() == 0:
            return body

        return selected_edges.chamfer(
            distance_mm
        )

    @staticmethod
    def linear_pattern(
        body: cq.Workplane,
        count_x: int,
        count_y: int,
        spacing_x: float,
        spacing_y: float,
    ) -> cq.Workplane:
        if count_x < 1 or count_y < 1:
            raise ValueError(
                "Los contadores del patrón deben ser mayores que cero."
            )

        return body.rarray(
            spacing_x,
            spacing_y,
            count_x,
            count_y,
        )

    @staticmethod
    def mirror(
        body: cq.Workplane,
        plane: str = "YZ",
    ) -> cq.Workplane:
        return body.mirror(
            plane
        )

    @staticmethod
    def offset2d(
        body: cq.Workplane,
        distance_mm: float,
    ) -> cq.Workplane:
        return body.offset2D(
            distance_mm
        )

    @staticmethod
    def _validate_positive(
        **values: float,
    ) -> None:
        for name, value in values.items():
            if value <= 0:
                raise ValueError(
                    f"{name} debe ser mayor que cero. "
                    f"Valor recibido: {value}"
                )