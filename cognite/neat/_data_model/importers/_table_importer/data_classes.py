from pydantic import BaseModel

from cognite.neat._utils.text import title_case
from cognite.neat._utils.useful_types import CellValue


class TableObj(BaseModel, extra="ignore", alias_generator=title_case): ...


class Metadata(TableObj):
    name: str
    value: str


class DMSProperty(TableObj):
    view: str
    view_property: str
    name: str
    description: str
    connection: str
    value_type: str
    min_count: int | None
    max_count: int | None
    immutable: bool | None
    default: CellValue | None
    container: str
    container_property: str
    container_property_name: str
    container_property_description: str
    index: str | None
    constraint: str | None


class DMSView(TableObj):
    view: str
    name: str | None
    description: str | None
    implements: str | None
    filter: str | None
    in_model: bool | None


class DMSContainer(TableObj):
    container: str
    name: str | None
    description: str | None
    constraint: str | None
    used_for: str | None


class TableDMS(TableObj):
    metadata: list[Metadata]
    properties: list[DMSProperty]
    views: list[DMSView]
    containers: list[DMSContainer]
