from typing import Annotated

from pydantic import AliasGenerator, BaseModel, BeforeValidator, Field
from pydantic.alias_generators import to_camel

from cognite.neat._data_model.models.entities import ParsedEntity, parse_entities, parse_entity
from cognite.neat._utils.text import title_case
from cognite.neat._utils.useful_types import CellValue

Entity = Annotated[ParsedEntity, BeforeValidator(parse_entity, str)]
EntityList = Annotated[list[ParsedEntity], BeforeValidator(parse_entities, str)]


class TableObj(
    BaseModel,
    extra="ignore",
    alias_generator=AliasGenerator(
        validation_alias=title_case,
        serialization_alias=to_camel,
    ),
): ...


class MetadataValue(TableObj):
    name: str
    value: CellValue


class DMSProperty(TableObj):
    view: Entity
    view_property: str
    name: str | None = None
    description: str | None = None
    connection: Entity | None
    value_type: Entity
    min_count: int | None
    max_count: int | None
    immutable: bool | None = None
    default: CellValue | None = None
    auto_increment: bool | None = None
    container: Entity | None = None
    container_property: str | None = None
    container_property_name: str | None = None
    container_property_description: str | None = None
    index: EntityList | None = None
    constraint: EntityList | None = None


class DMSView(TableObj):
    view: Entity
    name: str | None = None
    description: str | None = None
    implements: EntityList | None = None
    filter: str | None = None
    in_model: bool | None = None


class DMSContainer(TableObj):
    container: Entity
    name: str | None = None
    description: str | None = None
    constraint: EntityList | None = None
    used_for: str | None = None


class DMSEnum(TableObj):
    collection: str
    value: str
    name: str | None = None
    description: str | None = None


class DMSNode(TableObj):
    node: Entity


class TableDMS(TableObj):
    metadata: list[MetadataValue]
    properties: list[DMSProperty]
    views: list[DMSView]
    containers: list[DMSContainer] = Field(default_factory=list)
    enum: list[DMSEnum] = Field(default_factory=list)
    nodes: list[DMSNode] = Field(default_factory=list)
