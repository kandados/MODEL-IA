
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Point3D(BaseModel):
    x_mm: float
    y_mm: float
    z_mm: float


class BoundingBox(BaseModel):
    width_mm: float
    depth_mm: float
    height_mm: float


class Clearance(BaseModel):
    target: str
    value_mm: float
    reason: str


class Opening(BaseModel):
    target: str
    kind: Literal["port", "button", "speaker", "ventilation", "custom"]
    face: Optional[str] = None


class Support(BaseModel):
    target: str
    kind: Literal[
        "pcb_standoff",
        "battery_holder",
        "display_frame",
        "generic_support",
    ]
    quantity: int = 1


class MountFeature(BaseModel):
    target: str
    kind: Literal[
        "screw",
        "snap_fit",
        "heat_insert",
        "magnet",
        "adhesive",
    ]
    quantity: int = 1


class MechanicalDecision(BaseModel):
    category: str
    description: str
    priority: Literal["required", "recommended", "optional"] = "required"


class MechanicalPlan(BaseModel):
    version: str = "1.0"

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

    supports: list[Support] = Field(default_factory=list)

    openings: list[Opening] = Field(default_factory=list)

    mount_features: list[MountFeature] = Field(default_factory=list)

    clearances: list[Clearance] = Field(default_factory=list)

    reference_points: list[Point3D] = Field(default_factory=list)

    decisions: list[MechanicalDecision] = Field(default_factory=list)

    manufacturing_notes: list[str] = Field(default_factory=list)

    validation_rules: list[str] = Field(default_factory=list)

    overall_confidence: float = Field(default=1.0, ge=0.0, le=1.0)