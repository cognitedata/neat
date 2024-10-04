from pydantic import BaseModel, ConfigDict, Field

from cognite.neat.rules.models._types import ClassEntityType, InformationPropertyType


class PropertyRef(BaseModel):
    model_config = ConfigDict(
        frozen=True,
    )
    class_: ClassEntityType = Field(alias="Class")
    property_: InformationPropertyType = Field(alias="Property")


class ClassRef(BaseModel):
    model_config = ConfigDict(
        frozen=True,
    )
    class_: ClassEntityType = Field(alias="Class")


class PropertyMapping(BaseModel):
    source: PropertyRef
    destination: PropertyRef


class ClassMapping(BaseModel):
    source: ClassRef
    destination: ClassRef


class RuleMapping(BaseModel):
    properties: list[PropertyMapping]
    classes: list[ClassMapping]
