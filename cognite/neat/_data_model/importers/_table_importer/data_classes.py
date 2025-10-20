from collections.abc import Mapping
from typing import Annotated, Literal, cast, get_args

from pydantic import AliasGenerator, BaseModel, BeforeValidator, Field, PlainSerializer, model_validator
from pydantic.alias_generators import to_camel
from pydantic.fields import FieldInfo

from cognite.neat._data_model.models.entities import ParsedEntity, parse_entities, parse_entity
from cognite.neat._utils.text import title_case
from cognite.neat._utils.useful_types import CellValueType


def parse_entity_str(v: str) -> ParsedEntity:
    if isinstance(v, ParsedEntity):
        return v
    try:
        return parse_entity(v)
    except ValueError as e:
        raise ValueError(f"Invalid entity syntax: {e}") from e


def parse_entities_str(v: str) -> list[ParsedEntity] | None:
    if isinstance(v, list) and all(isinstance(item, ParsedEntity) for item in v):
        return v
    try:
        return parse_entities(v)
    except ValueError as e:
        raise ValueError(f"Invalid entity list syntax: {e}") from e


Entity = Annotated[ParsedEntity, BeforeValidator(parse_entity_str, str), PlainSerializer(func=str)]
EntityList = Annotated[
    list[ParsedEntity],
    BeforeValidator(parse_entities_str, str),
    PlainSerializer(func=lambda v: ",".join([str(item) for item in v])),
]


class TableObj(
    BaseModel,
    extra="ignore",
    alias_generator=AliasGenerator(
        alias=to_camel,
        validation_alias=title_case,
        serialization_alias=title_case,
    ),
    populate_by_name=True,
): ...


class MetadataValue(TableObj):
    key: str
    value: CellValueType


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
    default: CellValueType | None = None
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

    @model_validator(mode="before")
    def _title_case_keys(
        cls, data: dict[str, list[dict[str, CellValueType]]]
    ) -> dict[str, list[dict[str, CellValueType]]]:
        if isinstance(data, dict):
            # We are case-insensitive on the table names.
            return {title_case(k): v for k, v in data.items()}
        return data

    @classmethod
    def get_sheet_columns(
        cls, column_id: str, column: FieldInfo | None = None, *, column_type: Literal["all", "required"] = "required"
    ) -> list[str]:
        if column_id not in cls.model_fields.keys():
            raise KeyError(f"Invalid field id: {column_id}")
        if column is None:
            column = cls.model_fields[column_id]
        return [
            # We know all fields has validation_alias because of the alias_generator in TableDMS
            cast(str, sheet_field.validation_alias)
            # All the fields in the sheet's model are lists.
            for sheet_field in get_args(column.annotation)[0].model_fields.values()
            if sheet_field.is_required() or column_type == "all"
        ]

    @classmethod
    def get_sheet_column_by_alias(
        cls, field_alias: str, *, field_type: Literal["all", "required"] = "required"
    ) -> list[str]:
        for field_id, field_ in cls.model_fields.items():
            if cast(str, field_.validation_alias) == field_alias:
                return cls.get_sheet_columns(field_id, field_, column_type=field_type)
        raise KeyError(f"Invalid field alias: {field_alias}")

    @classmethod
    def required_sheets(cls) -> set[str]:
        return {cast(str, field_.validation_alias) for field_ in cls.model_fields.values() if field_.is_required()}


DMS_API_MAPPING: Mapping[str, Mapping[str, str]] = {
    "Views": {
        "space": "View",
        "externalId": "View",
        "version": "View",
        **{
            cast(str, field_.alias): cast(str, field_.validation_alias)
            for field_id, field_ in DMSView.model_fields.items()
            if field_id != "View"
        },
    },
    "Containers": {
        "space": "Container",
        "externalId": "Container",
        **{
            cast(str, field_.alias): cast(str, field_.validation_alias)
            for field_id, field_ in DMSContainer.model_fields.items()
            if field_id != "Container"
        },
    },
    "Properties": {
        "space": "View",
        "externalId": "View",
        "property": "ViewProperty",
        **{
            cast(str, field_.alias): cast(str, field_.validation_alias)
            for field_id, field_ in DMSProperty.model_fields.items()
            if field_id not in ("View", "ViewProperty")
        },
    },
}
