import re
from abc import ABC
from collections.abc import Mapping
from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, field_validator

from cognite.neat._utils.auxiliary import get_concrete_subclasses
from cognite.neat._utils.useful_types import BaseModelObject

from ._constants import ENUM_VALUE_IDENTIFIER_PATTERN, FORBIDDEN_ENUM_VALUES, INSTANCE_ID_PATTERN
from ._references import ContainerReference, ViewReference


class PropertyTypeDefinition(BaseModelObject, ABC):
    type: str


class ListablePropertyTypeDefinition(PropertyTypeDefinition, ABC):
    list: bool | None = Field(
        default=None,
        description="Specifies that the data type is a list of values.",
    )
    max_list_size: int | None = Field(
        default=None,
        description="Specifies the maximum number of values in the list",
    )


class TextProperty(ListablePropertyTypeDefinition):
    type: Literal["text"] = "text"
    max_text_size: int | None = Field(
        default=None,
        description="Specifies the maximum size in bytes of the text property, when encoded with utf-8.",
    )
    collation: str | None = Field(
        default=None,
        description="he set of language specific rules - used when sorting text fields.",
    )


class Unit(BaseModelObject):
    external_id: str = Field(
        description="The external ID of the unit. Must match the unit in the Cognite Unit catalog.",
        min_length=1,
        max_length=256,
        pattern=INSTANCE_ID_PATTERN,
    )
    source_unit: str | None = Field(
        default=None,
        description="The unit in the source system.",
    )


class FloatProperty(ListablePropertyTypeDefinition, ABC):
    unit: Unit | None = Field(default=None, description="The unit of the data stored in this property", exclude=False)


class Float32Property(FloatProperty):
    type: Literal["float32"] = "float32"


class Float64Property(FloatProperty):
    type: Literal["float64"] = "float64"


class BooleanProperty(ListablePropertyTypeDefinition):
    type: Literal["boolean"] = "boolean"


class Int32Property(ListablePropertyTypeDefinition):
    type: Literal["int32"] = "int32"


class Int64Property(ListablePropertyTypeDefinition):
    type: Literal["int64"] = "int64"


class TimestampProperty(ListablePropertyTypeDefinition):
    type: Literal["timestamp"] = "timestamp"


class DateProperty(ListablePropertyTypeDefinition):
    type: Literal["date"] = "date"


class JSONProperty(ListablePropertyTypeDefinition):
    type: Literal["json"] = "json"


class TimeseriesCDFExternalIdReference(ListablePropertyTypeDefinition):
    type: Literal["timeseries"] = "timeseries"


class FileCDFExternalIdReference(ListablePropertyTypeDefinition):
    type: Literal["file"] = "file"


class SequenceCDFExternalIdReference(ListablePropertyTypeDefinition):
    type: Literal["sequence"] = "sequence"


class DirectNodeRelation(ListablePropertyTypeDefinition):
    type: Literal["direct"] = "direct"
    container: ContainerReference | None = Field(
        default=None,
        description="The (optional) required type for the node the direct relation points to.  If specified, "
        "the node must exist before the direct relation is referenced and of the specified type. "
        "If no container specification is used, the node will be auto created with the built-in node "
        "container type, and it does not explicitly have to be created before the node that references it.",
    )
    # This property is only available in the response object. It will be ignored in the request object.
    # In the request object, use ViewCoreProperty.source instead.
    source: ViewReference | None = Field(
        None, description="The hint showing the view what the direct relation points to.", exclude=True
    )


class EnumValue(BaseModelObject):
    name: str | None = Field(
        None,
        max_length=255,
        description="The name of the enum value.",
    )
    description: str | None = Field(
        default=None,
        max_length=1024,
        description="Description of the enum value.",
    )


_ENUM_KEY = re.compile(ENUM_VALUE_IDENTIFIER_PATTERN)


class EnumProperty(PropertyTypeDefinition):
    type: Literal["enum"] = "enum"
    unknown_value: str | None = Field(
        default=None,
        description="TThe value to use when the enum value is unknown. This can optionally be used to "
        "provide forward-compatibility, Specifying what value to use if the client does not "
        "recognize the returned value. It is not possible to ingest the unknown value, "
        "but it must be part of the allowed values.",
        min_length=1,
        max_length=128,
        pattern=ENUM_VALUE_IDENTIFIER_PATTERN,
    )
    values: dict[str, EnumValue] = Field(
        description="A set of all possible values for the enum property.",
        min_length=1,
        max_length=32,
    )

    @field_validator("values", mode="after")
    def _valid_enum_value(cls, val: dict[str, EnumValue]) -> dict[str, EnumValue]:
        errors: list[str] = []
        for key in val.keys():
            if not _ENUM_KEY.match(key):
                errors.append(
                    f"Enum value {key!r} is not valid. Enum values must match "
                    f"the pattern: {ENUM_VALUE_IDENTIFIER_PATTERN}"
                )
            if len(key) > 128 or len(key) < 1:
                errors.append(f"Enum value {key!r} must be between 1 and 128 characters long.")
            if key.lower() in FORBIDDEN_ENUM_VALUES:
                errors.append(
                    f"Enum value {key!r} cannot be any of the following reserved values: {FORBIDDEN_ENUM_VALUES}"
                )
        if errors:
            raise ValueError(";".join(errors))
        return val


DataType = Annotated[
    TextProperty
    | Float32Property
    | Float64Property
    | BooleanProperty
    | Int32Property
    | Int64Property
    | TimestampProperty
    | DateProperty
    | JSONProperty
    | TimeseriesCDFExternalIdReference
    | FileCDFExternalIdReference
    | SequenceCDFExternalIdReference
    | DirectNodeRelation
    | EnumProperty,
    Field(discriminator="type"),
]

DataTypeAdapter: TypeAdapter[DataType] = TypeAdapter(DataType)

DMS_DATA_TYPES: Mapping[str, type[PropertyTypeDefinition]] = {
    cls_.model_fields["type"].default: cls_ for cls_ in get_concrete_subclasses(PropertyTypeDefinition)
}
