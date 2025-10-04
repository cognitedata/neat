from pydantic import AliasGenerator, BaseModel, Field
from pydantic.alias_generators import to_camel

from cognite.neat._utils.text import title_case
from cognite.neat._utils.useful_types import CellValue


class TableObj(
    BaseModel,
    extra="ignore",
    alias_generator=AliasGenerator(
        validation_alias=title_case,
        serialization_alias=to_camel,
    ),
): ...


class Metadata(TableObj):
    name: str
    value: str


class DMSProperty(TableObj):
    view: str
    view_property: str
    name: str | None = None
    description: str | None = None
    connection: str | None = None
    value_type: str
    min_count: int | None
    max_count: int | None
    immutable: bool | None = None
    default: CellValue | None = None
    container: str
    container_property: str
    container_property_name: str | None = None
    container_property_description: str | None = None
    index: str | None = None
    constraint: str | None = None


class DMSView(TableObj):
    view: str
    name: str | None = None
    description: str | None = None
    implements: str | None = None
    filter: str | None = None
    in_model: bool | None = None


class DMSContainer(TableObj):
    container: str
    name: str | None = None
    description: str | None = None
    constraint: str | None = None
    used_for: str | None = None


class TableDMS(TableObj):
    metadata: list[Metadata]
    properties: list[DMSProperty]
    views: list[DMSView]
    containers: list[DMSContainer] = Field(default_factory=list)
