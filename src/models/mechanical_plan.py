from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


GeometricAnchor = Literal[
    "global_origin",
    "external_center",
    "interior_center",
    "floor_center",
    "ceiling_center",
    "left_wall_center",
    "right_wall_center",
    "front_wall_center",
    "rear_wall_center",
    "bottom_left",
    "bottom_right",
    "top_left",
    "top_right",
]


class Point3D(BaseModel):
    """Punto cartesiano expresado en milímetros."""

    x_mm: float
    y_mm: float
    z_mm: float


class Offset3D(BaseModel):
    """
    Desplazamiento relativo respecto a un anclaje geométrico.

    Los tres valores se expresan en milímetros.
    """

    x_mm: float = 0.0
    y_mm: float = 0.0
    z_mm: float = 0.0


class BoundingBox(BaseModel):
    """Dimensiones de un volumen rectangular."""

    width_mm: float
    depth_mm: float
    height_mm: float


class InteriorMargins(BaseModel):
    """
    Márgenes de seguridad aplicados sobre el volumen interior real.

    Permiten reservar espacio respecto a paredes, suelo y techo sin
    modificar las dimensiones físicas de la carcasa.
    """

    left_mm: float = Field(default=0.0, ge=0.0)
    right_mm: float = Field(default=0.0, ge=0.0)
    front_mm: float = Field(default=0.0, ge=0.0)
    rear_mm: float = Field(default=0.0, ge=0.0)
    floor_mm: float = Field(default=0.0, ge=0.0)
    ceiling_mm: float = Field(default=0.0, ge=0.0)


class ComponentDimensions(BaseModel):
    """
    Dimensiones físicas aproximadas de un componente.

    Estas dimensiones se utilizarán posteriormente para comprobar:

    - límites interiores;
    - colisiones;
    - separación entre componentes;
    - generación de soportes.
    """

    width_mm: float = Field(gt=0.0)
    depth_mm: float = Field(gt=0.0)
    height_mm: float = Field(gt=0.0)


class ComponentPlacement(BaseModel):
    """
    Colocación paramétrica de un componente.

    La posición nunca se define inicialmente mediante coordenadas absolutas.
    Se define mediante un anclaje geométrico y un desplazamiento relativo.
    """

    target: str

    anchor: GeometricAnchor = "interior_center"

    offset: Offset3D = Field(default_factory=Offset3D)

    dimensions: Optional[ComponentDimensions] = None

    rotation_z_deg: float = 0.0

    clearance_mm: float = Field(default=0.0, ge=0.0)

    allow_overlap: bool = False


class ReservedZone(BaseModel):
    """
    Región del volumen interior que no debe ser ocupada automáticamente.

    Se utilizará para reservar espacio para:

    - cableado;
    - conectores;
    - ventilación;
    - mecanismos de cierre;
    - zonas de mantenimiento.
    """

    name: str

    anchor: GeometricAnchor = "interior_center"

    offset: Offset3D = Field(default_factory=Offset3D)

    dimensions: ComponentDimensions

    reason: str


class Clearance(BaseModel):
    target: str
    value_mm: float
    reason: str


class Opening(BaseModel):
    target: str
    kind: Literal[
        "port",
        "button",
        "speaker",
        "ventilation",
        "custom",
    ]
    face: Optional[str] = None


class Support(BaseModel):
    target: str
    kind: Literal[
        "pcb_standoff",
        "battery_holder",
        "display_frame",
        "generic_support",
    ]
    quantity: int = Field(default=1, ge=1)


class MountFeature(BaseModel):
    target: str
    kind: Literal[
        "screw",
        "snap_fit",
        "heat_insert",
        "magnet",
        "adhesive",
    ]
    quantity: int = Field(default=1, ge=1)


class MechanicalDecision(BaseModel):
    category: str
    description: str
    priority: Literal[
        "required",
        "recommended",
        "optional",
    ] = "required"


class MechanicalPlan(BaseModel):
    """
    Plan mecánico independiente del motor CAD.

    El plan describe:

    - dimensiones generales;
    - componentes internos;
    - soportes;
    - aberturas;
    - fijaciones;
    - colocaciones paramétricas;
    - márgenes;
    - zonas reservadas.

    Los builders CAD consumen este modelo, pero no deben decidir por sí
    mismos dónde se encuentra cada componente.
    """

    version: str = "1.1"

    enclosure_type: Literal[
        "box",
        "case",
        "support",
        "adapter",
        "mount",
        "custom",
    ] = "case"

    external_bounding_box: Optional[BoundingBox] = None

    internal_components: list[str] = Field(default_factory=list)

    component_placements: list[ComponentPlacement] = Field(
        default_factory=list
    )

    interior_margins: InteriorMargins = Field(
        default_factory=InteriorMargins
    )

    reserved_zones: list[ReservedZone] = Field(default_factory=list)

    supports: list[Support] = Field(default_factory=list)

    openings: list[Opening] = Field(default_factory=list)

    mount_features: list[MountFeature] = Field(default_factory=list)

    clearances: list[Clearance] = Field(default_factory=list)

    reference_points: list[Point3D] = Field(default_factory=list)

    decisions: list[MechanicalDecision] = Field(default_factory=list)

    manufacturing_notes: list[str] = Field(default_factory=list)

    validation_rules: list[str] = Field(default_factory=list)

    overall_confidence: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
    )