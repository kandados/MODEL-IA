from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field

class Identity(BaseModel):
    manufacturer:str=""
    model:str=""
    family:Optional[str]=None
    version:Optional[str]=None
    aliases:list[str]=Field(default_factory=list)

class Dimensions(BaseModel):
    width_mm:Optional[float]=None
    depth_mm:Optional[float]=None
    height_mm:Optional[float]=None
    weight_kg:Optional[float]=None

class BoundingBox(BaseModel):
    x_mm:Optional[float]=None
    y_mm:Optional[float]=None
    z_mm:Optional[float]=None

class Material(BaseModel):
    name:str
    location:Optional[str]=None
    confidence:float=Field(default=1.0,ge=0.0,le=1.0)

class MountPoint(BaseModel):
    name:str
    x_mm:Optional[float]=None
    y_mm:Optional[float]=None
    z_mm:Optional[float]=None

class Connector(BaseModel):
    name:str
    type:str
    connected_to:Optional[str]=None

class Component(BaseModel):
    id:str
    type:str
    name:str
    manufacturer:Optional[str]=None
    model:Optional[str]=None
    dimensions:Dimensions=Field(default_factory=Dimensions)
    material:Optional[str]=None
    mass_kg:Optional[float]=None
    position:dict[str,float]=Field(default_factory=dict)
    rotation:dict[str,float]=Field(default_factory=dict)
    bounding_box:BoundingBox=Field(default_factory=BoundingBox)
    mounting_points:list[MountPoint]=Field(default_factory=list)
    connectors:list[Connector]=Field(default_factory=list)
    properties:dict[str,Any]=Field(default_factory=dict)

class Port(BaseModel):
    type:str
    face:Optional[str]=None
    count:int=1
    coordinates_known:bool=False

class Button(BaseModel):
    name:str
    face:Optional[str]=None
    coordinates_known:bool=False

class Fastener(BaseModel):
    type:str
    quantity:int=1
    size:Optional[str]=None

class Relationship(BaseModel):
    source:str
    relation:str
    target:str

class Constraint(BaseModel):
    category:str
    description:str
    critical:bool=True
    value:Optional[float]=None
    unit:Optional[str]=None

class Manufacturing(BaseModel):
    supported_processes:list[str]=Field(default_factory=list)
    preferred_process:Optional[str]=None

class Reference(BaseModel):
    title:str
    source_id:Optional[str]=None
    url:Optional[str]=None

class EngineeringKnowledge(BaseModel):
    identity:Identity
    dimensions:Dimensions=Field(default_factory=Dimensions)
    materials:list[Material]=Field(default_factory=list)
    components:list[Component]=Field(default_factory=list)
    ports:list[Port]=Field(default_factory=list)
    buttons:list[Button]=Field(default_factory=list)
    fasteners:list[Fastener]=Field(default_factory=list)
    relationships:list[Relationship]=Field(default_factory=list)
    constraints:list[Constraint]=Field(default_factory=list)
    manufacturing:Manufacturing=Field(default_factory=Manufacturing)
    references:list[Reference]=Field(default_factory=list)
    overall_confidence:float=Field(default=1.0,ge=0.0,le=1.0)