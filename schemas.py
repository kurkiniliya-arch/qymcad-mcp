"""Validated tool arguments; dimensions are in millimetres."""
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

Size = Annotated[float, Field(ge=0.01, le=10000, allow_inf_nan=False)]
Coordinate = Annotated[float, Field(ge=-10000, le=10000, allow_inf_nan=False)]
NodeId = Annotated[int, Field(gt=0)]
Name = Annotated[str, Field(min_length=1, max_length=128)]
Expression = Annotated[str, Field(min_length=1, max_length=256)]

class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Point(Record):
    x: Coordinate = 0
    y: Coordinate = 0

class Vector(Point):
    z: Coordinate = 0

class BoxSize(Record):
    x: Size
    y: Size
    z: Size

class Box(Record):
    kind: Literal["box"]
    size: BoxSize

class Cylinder(Record):
    kind: Literal["cylinder"]
    radius: Size
    height: Size

class Sphere(Record):
    kind: Literal["sphere"]
    radius: Size

class Cone(Record):
    kind: Literal["cone"]
    bottom_radius: Size
    top_radius: Annotated[float, Field(ge=0, le=10000, allow_inf_nan=False)]
    height: Size

class Torus(Record):
    kind: Literal["torus"]
    major_radius: Size
    minor_radius: Size

Primitive = Annotated[Box | Cylinder | Sphere | Cone | Torus, Field(discriminator="kind")]

class Rectangle(Record):
    kind: Literal["rectangle"]
    origin: Point = Field(default_factory=Point)
    size: Point

class Circle(Record):
    kind: Literal["circle"]
    center: Point = Field(default_factory=Point)
    radius: Size

class Polygon(Record):
    kind: Literal["polygon"]
    points: Annotated[list[Point], Field(min_length=3, max_length=256)]

Profile = Annotated[Rectangle | Circle | Polygon, Field(discriminator="kind")]

