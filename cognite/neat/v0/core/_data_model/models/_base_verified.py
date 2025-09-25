"""This module contains the definition of `DataModel` pydantic model and all
its sub-models and validators.
"""

import math
import sys
import types
from abc import ABC, abstractmethod
from collections.abc import Callable, Hashable, Iterator, MutableSequence, Sequence
from datetime import datetime
from typing import Annotated, Any, ClassVar, Literal, SupportsIndex, TypeVar, get_args, get_origin, overload

import pandas as pd
from cognite.client import data_modeling as dm
from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    GetCoreSchemaHandler,
    PlainSerializer,
    field_validator,
    model_serializer,
)
from pydantic.main import IncEx
from pydantic_core import core_schema
from rdflib import Namespace, URIRef

from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE
from cognite.neat.v0.core._data_model.models._types import (
    ContainerEntityType,
    DataModelExternalIdType,
    PhysicalPropertyType,
    SpaceType,
    StrListType,
    URIRefType,
    VersionType,
    ViewEntityType,
)
from cognite.neat.v0.core._data_model.models.data_types import DataType
from cognite.neat.v0.core._data_model.models.entities import (
    EdgeEntity,
    ReverseConnectionEntity,
    ViewEntity,
)
from cognite.neat.v0.core._utils.rdf_ import uri_display_name

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum


METADATA_VALUE_MAX_LENGTH = 5120


def _get_required_fields(model: type[BaseModel], use_alias: bool = False) -> set[str]:
    """Get required fields from a pydantic model.

    Parameters
    ----------
    model : type[BaseModel]
        Pydantic data model
    use_alias : bool, optional
        Whether to return field alias name, by default False

    Returns
    -------
    list[str]
        List of required fields
    """
    required_fields = set()
    for name, field in model.model_fields.items():
        if not field.is_required():
            continue

        alias = getattr(field, "alias", None)
        if use_alias and alias:
            required_fields.add(alias)
        else:
            required_fields.add(name)
    return required_fields


class SchemaCompleteness(StrEnum):
    complete = "complete"
    partial = "partial"
    extended = "extended"


class ExtensionCategory(StrEnum):
    addition = "addition"
    reshape = "reshape"
    rebuild = "rebuild"


class DataModelType(StrEnum):
    solution = "solution"
    enterprise = "enterprise"


class DataModelLevel(StrEnum):
    conceptual = "conceptual"
    logical = "logical"
    physical = "physical"


class RoleTypes(StrEnum):
    information = "information architect"
    dms = "DMS Architect"


class SchemaModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=True,
        strict=False,
        extra="ignore",
        use_enum_values=True,
    )

    @classmethod
    def mandatory_fields(cls: Any, use_alias: bool = False) -> set[str]:
        """Returns a set of mandatory fields for the model."""
        return _get_required_fields(cls, use_alias)

    @field_validator("*", mode="before")
    def strip_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        elif isinstance(value, list):
            return [entry.strip() if isinstance(entry, str) else entry for entry in value]
        return value


class BaseVerifiedMetadata(SchemaModel):
    """
    Metadata model for data model
    """

    role: ClassVar[RoleTypes] = Field(description="Role of the person creating the data model")
    level: ClassVar[DataModelLevel] = Field(description="Aspect of the data model")
    space: SpaceType = Field(description="The space where the data model is defined")
    external_id: DataModelExternalIdType = Field(
        alias="externalId", description="External identifier for the data model"
    )
    version: VersionType = Field(description="Version of the data model")

    name: str | None = Field(
        None,
        description="Human readable name of the data model",
        min_length=1,
        max_length=255,
    )

    description: str | None = Field(
        None, min_length=1, max_length=1024, description="Short description of the data model"
    )

    creator: StrListType = Field(
        description=(
            "List of contributors (comma separated) to the data model creation, "
            "typically information architects are considered as contributors."
        ),
    )

    created: datetime = Field(
        description="Date of the data model creation",
    )

    updated: datetime = Field(
        description="Date of the data model update",
    )

    source_id: URIRefType | None = Field(
        None,
        description="Id of source that produced this data model",
        alias="sourceId",
    )

    @field_validator("*", mode="before")
    def strip_string(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("description", mode="before")
    def nan_as_none(cls: Any, value: Any) -> Any:
        if isinstance(value, float) and math.isnan(value):
            return None
        return value

    def to_pandas(self) -> pd.Series:
        """Converts Metadata to pandas Series."""
        return pd.Series(self.model_dump())

    def _repr_html_(self) -> str:
        """Returns HTML representation of Metadata."""
        return self.to_pandas().to_frame("value")._repr_html_()  # type: ignore[operator]

    @classmethod
    def mandatory_fields(cls: Any, use_alias: bool = False) -> set[str]:
        """Returns a set of mandatory fields for the model."""
        return _get_required_fields(cls, use_alias)

    @model_serializer(mode="wrap")
    def include_role(self, serializer: Callable) -> dict:
        return {"role": self.role.value, **serializer(self)}

    @property
    def prefix(self) -> str:
        return self.space

    def get_prefix(self) -> str:
        return self.prefix

    @property
    def identifier(self) -> URIRef:
        """Globally unique identifier for the data model.

        !!! note
            Unlike namespace, the identifier does not end with "/" or "#".

        """
        return DEFAULT_NAMESPACE[f"data-model/verified/{self.level}/{self.space}/{self.external_id}/{self.version}"]

    @property
    def namespace(self) -> Namespace:
        """Namespace for the data model used for the entities in the data model."""
        return Namespace(f"{self.identifier}/")

    def as_data_model_id(self) -> dm.DataModelId:
        return dm.DataModelId(space=self.space, external_id=self.external_id, version=self.version)

    def as_identifier(self) -> str:
        return repr(self.as_data_model_id())

    @classmethod
    def default(cls) -> "BaseVerifiedMetadata":
        """Returns a default instance of the metadata model."""
        now = datetime.now()
        return cls(
            space="pleaseUpdateMe",
            external_id="PleaseUpdateMe",
            version="v1",
            name="Please Update Me",
            description="Please Update Me",
            creator=["NEAT"],
            created=now,
            updated=now,
        )


class BaseVerifiedDataModel(SchemaModel, ABC):
    """
    Data Model is a core concept in `neat`.

    Args:
        metadata: Data model metadata
    """

    metadata: BaseVerifiedMetadata

    @classmethod
    def headers_by_sheet(cls, by_alias: bool = False) -> dict[str, list[str]]:
        """Returns a list of headers for the model, typically used by ExcelExporter"""
        headers_by_sheet: dict[str, list[str]] = {}
        for field_name, field in cls.model_fields.items():
            if field_name in ["validators_to_skip", "post_validate"]:
                continue
            sheet_name = (field.alias or field_name) if by_alias else field_name
            annotation = field.annotation

            if isinstance(annotation, types.UnionType):
                annotation = annotation.__args__[0]

            try:
                if isinstance(annotation, types.GenericAlias) and get_origin(annotation).__name__ == SheetList.__name__:
                    # We know that this is a SheetList, so we can safely access the annotation
                    # which is the concrete type of the SheetEntity.
                    model_fields = get_args(annotation)[0].model_fields  # type: ignore[union-attr]
                elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
                    model_fields = annotation.model_fields
                else:
                    model_fields = {}
            except TypeError:
                # Python 3.10 raises TypeError: issubclass() arg 1 must be a class
                # when calling issubclass(annotation, SheetList) with the dict annotation
                model_fields = {}
            headers_by_sheet[sheet_name] = [
                (field.alias or field_name) if by_alias else field_name
                for field_name, field in model_fields.items()
                if field_name != "validators_to_skip" and not field.exclude
            ]
        return headers_by_sheet

    @property
    def display_name(self) -> str:
        return uri_display_name(self.metadata.identifier)

    def dump(
        self,
        entities_exclude_defaults: bool = True,
        sort: bool = False,
        mode: Literal["python", "json"] = "python",
        by_alias: bool = False,
        exclude: IncEx | None = None,
        exclude_none: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
    ) -> dict[str, Any]:
        """Dump the model to a dictionary.

        This is used in the Exporters to the dump data model in the required format.

        Args:
            entities_exclude_defaults: Whether to exclude default prefix (and version) for entities.
                For example, given a class that is dumped as 'my_prefix:MyClass', if the prefix for the data model
                set in metadata.prefix = 'my_prefix', then this class will be dumped as 'MyClass' when this flag is set.
                Defaults to True.
            sort: Whether to sort the entities in the output.
            mode: The mode in which `to_python` should run.
                If mode is 'json', the output will only contain JSON serializable types.
                If mode is 'python', the output may contain non-JSON-serializable Python objects.
            by_alias: Whether to use the field's alias in the dictionary key if defined.
            exclude: A set of fields to exclude from the output.
            exclude_none: Whether to exclude fields that have a value of `None`.
            exclude_unset: Whether to exclude fields that have not been explicitly set.
            exclude_defaults: Whether to exclude fields that are set to their default value.
        """
        if sort:
            for field_name in self.model_fields.keys():
                value = getattr(self, field_name)
                # Ensure deterministic order of properties, classes, views, and so on
                if isinstance(value, SheetList):
                    value.sort(key=lambda x: x._identifier())

        context: dict[str, Any] = {}
        if entities_exclude_defaults:
            context["metadata"] = self.metadata

        exclude_input: IncEx | None = exclude

        return self.model_dump(
            mode=mode,
            by_alias=by_alias,
            exclude=exclude_input,
            exclude_none=exclude_none,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            context=context,
        )


class SheetRow(SchemaModel):
    neatId: URIRefType | None = Field(
        alias="Neat ID",
        description="Globally unique identifier for the property",
        default=None,
    )

    @abstractmethod
    def _identifier(self) -> tuple[Hashable, ...]:
        raise NotImplementedError()

    def __repr__(self) -> str:
        # Simplified representation of the object for debugging
        return f"{self.__class__.__name__}({self._identifier()})"


T_SheetRow = TypeVar("T_SheetRow", bound=SheetRow)


class SheetList(list, MutableSequence[T_SheetRow]):
    @classmethod
    def __get_pydantic_core_schema__(cls, source: Any, handler: GetCoreSchemaHandler) -> core_schema.CoreSchema:
        if args := get_args(source):
            item_type = args[0]
        else:
            # Someone use SheetList without specifying the type
            raise TypeError("SheetList must be used with a type argument, e.g., SheetList[InformationProperty]")

        instance_schema = core_schema.is_instance_schema(cls)
        sequence_row_schema = handler.generate_schema(Sequence[item_type])  # type: ignore[valid-type]

        non_instance_schema = core_schema.no_info_after_validator_function(SheetList, sequence_row_schema)
        return core_schema.union_schema([instance_schema, non_instance_schema])

    def to_pandas(self, drop_na_columns: bool = True, include: list[str] | None = None) -> pd.DataFrame:
        """Converts ResourceDict to pandas DataFrame."""
        df = pd.DataFrame([entity.model_dump() for entity in self])
        if drop_na_columns:
            df = df.dropna(axis=1, how="all")
        if include is not None:
            df = df[include]
        return df

    def _repr_html_(self) -> str:
        """Returns HTML representation of ResourceDict."""
        df = self.to_pandas(drop_na_columns=True)
        if "neatId" in df.columns:
            df = df.drop(columns=["neatId"])
        return df._repr_html_()  # type: ignore[operator]

    # Implemented to get correct type hints
    def __iter__(self) -> Iterator[T_SheetRow]:
        return super().__iter__()

    @overload
    def __getitem__(self, index: SupportsIndex) -> T_SheetRow: ...

    @overload
    def __getitem__(self, index: slice) -> "SheetList[T_SheetRow]": ...

    def __getitem__(self, index: SupportsIndex | slice, /) -> "T_SheetRow | SheetList[T_SheetRow]":
        if isinstance(index, slice):
            return SheetList[T_SheetRow](super().__getitem__(index))
        return super().__getitem__(index)


ExtensionCategoryType = Annotated[
    ExtensionCategory,
    PlainSerializer(
        lambda v: v.value if isinstance(v, ExtensionCategory) else v,
        return_type=str,
        when_used="unless-none",
    ),
    BeforeValidator(lambda v: ExtensionCategory(v) if isinstance(v, str) else v),
]


# Immutable such that this can be used as a key in a dictionary
class ContainerProperty(BaseModel, frozen=True):
    container: ContainerEntityType
    property_: PhysicalPropertyType


class ContainerDestinationProperty(ContainerProperty, frozen=True):
    value_type: DataType | ViewEntity
    connection: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None = None


class ViewRef(BaseModel, frozen=True):
    view: ViewEntityType


class ViewProperty(ViewRef, frozen=True):
    property_: PhysicalPropertyType
