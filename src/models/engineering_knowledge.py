from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Dimensions(BaseModel):
    width_mm: Optional[float] = None
    depth_mm: Optional[float] = None
    height_mm: Optional[float] = None
    weight_kg: Optional[float] = None


class Material(BaseModel):
    name: str
    location: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)


class Port(BaseModel):
    type: str
    face: Optional[str] = None
    count: int = 1
    coordinates_known: bool = False


class Button(BaseModel):
    name: str
    face: Optional[str] = None
    coordinates_known: bool = False


class Ventilation(BaseModel):
    bottom_airflow: bool = False
    rear_airflow: bool = False
    left_airflow: bool = False
    right_airflow: bool = False
    top_airflow: bool = False
    minimum_clearance_mm: Optional[float] = None


class Constraint(BaseModel):
    description: str
    critical: bool = True


class EngineeringKnowledge(BaseModel):
    manufacturer: str
    model: str

    dimensions: Dimensions = Field(default_factory=Dimensions)

    materials: list[Material] = Field(default_factory=list)

    ports: list[Port] = Field(default_factory=list)

    buttons: list[Button] = Field(default_factory=list)

    ventilation: Ventilation = Field(default_factory=Ventilation)

    constraints: list[Constraint] = Field(default_factory=list)

    overall_confidence: float = Field(ge=0.0, le=1.0)