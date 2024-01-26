"""This module contains the definition of `TransformationRules` pydantic model and all
its sub-models and validators.
"""

from __future__ import annotations

import math
import sys
from datetime import datetime
from functools import wraps
from typing import ClassVar, TypeAlias

import pandas as pd
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    constr,
)
from pydantic.fields import FieldInfo
from rdflib import Namespace

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum

#     "Class",
#     "Classes",
#     "Instance",
#     "CoreMetadata",
#     "Prefixes",
#     "Property",
#     "Properties",
#     "Resource",
#     "Rules",

METADATA_VALUE_MAX_LENGTH = 5120


def replace_nan_floats_with_default(values: dict, model_fields: dict[str, FieldInfo]) -> dict:
    output = {}
    for field_name, value in values.items():
        is_nan_float = isinstance(value, float) and math.isnan(value)
        if not is_nan_float:
            output[field_name] = value
            continue
        if field_name in model_fields:
            output[field_name] = model_fields[field_name].default
        else:
            # field_name may be an alias
            source_name = next((name for name, field in model_fields.items() if field.alias == field_name), None)
            if source_name:
                output[field_name] = model_fields[source_name].default
            else:
                # Just pass it through if it is not an alias.
                output[field_name] = value
    return output


def skip_field_validator(validators_field):
    def decorator(func):
        @wraps(func)
        def wrapper(cls, value, values):
            if isinstance(values, dict):
                to_skip = values.get(validators_field, set())
            else:
                try:
                    to_skip = values.data.get(validators_field, set())
                except Exception:
                    to_skip = set()

            if "all" in to_skip or func.__name__ in to_skip:
                return value
            return func(cls, value, values)

        return wrapper

    return decorator


def skip_model_validator(validators_field):
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            to_skip = getattr(self, validators_field, set())
            if "all" in to_skip or func.__name__ in to_skip:
                return self

            return func(self)

        return wrapper

    return decorator


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


########################################################################################
### These highly depend on CDF API endpoint limitations we need to keep them updated ###
########################################################################################
more_than_one_none_alphanumerics_regex = r"([_-]{2,})"

prefix_compliance_regex = r"^([a-zA-Z]+)([a-zA-Z0-9]*[_-]{0,1}[a-zA-Z0-9_-]*)([a-zA-Z0-9]*)$"
data_model_id_compliance_regex = r"^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$"
cdf_space_compliance_regex = (
    r"(?!^(space|cdf|dms|pg3|shared|system|node|edge)$)(^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$)"
)

view_id_compliance_regex = (
    r"(?!^(Query|Mutation|Subscription|String|Int32|Int64|Int|Float32|Float64|Float|"
    r"Timestamp|JSONObject|Date|Numeric|Boolean|PageInfo|File|Sequence|TimeSeries)$)"
    r"(^[a-zA-Z][a-zA-Z0-9_]{0,253}[a-zA-Z0-9]?$)"
)
dms_property_id_compliance_regex = (
    r"(?!^(space|externalId|createdTime|lastUpdatedTime|deletedTime|edge_id|"
    r"node_id|project_id|property_group|seq|tg_table_name|extensions)$)"
    r"(^[a-zA-Z][a-zA-Z0-9_]{0,253}[a-zA-Z0-9]?$)"
)


class_id_compliance_regex = r"(?!^(Class|class)$)(^[a-zA-Z][a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]?$)"
property_id_compliance_regex = r"^(\*)|(?!^(Property|property)$)(^[a-zA-Z][a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]?$)"

version_compliance_regex = r"^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$"
########################################################################################
########################################################################################

Prefix: TypeAlias = str
ExternalId: TypeAlias = str
Space: TypeAlias = str
Description: TypeAlias = constr(min_length=1, max_length=1024)  # type: ignore[valid-type]


class RoleTypes(StrEnum):
    domain_expert = "domain expert"
    information_architect = "information architect"
    cdf_solution_architect = "cdf solution architect"


class RuleModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=True,
        strict=False,
        extra="allow",
        use_enum_values=True,
    )
    validators_to_skip: set[str] = Field(default_factory=set, exclude=True)

    @classmethod
    def mandatory_fields(cls, use_alias=False) -> set[str]:
        """Returns a set of mandatory fields for the model."""
        return _get_required_fields(cls, use_alias)


class URL(BaseModel):
    url: HttpUrl


class CoreMetadata(RuleModel):
    """
    Metadata model for data model

    """

    role: RoleTypes | None = Field(description=("Role of the person who creates the data model"), default=None)

    prefix: Prefix | None = Field(
        description=("This is used as a short form for namespace"),
        default=None,
    )

    namespace: Namespace | None = Field(
        description="This is used as RDF namespace for generation of semantic data model representation",
        min_length=1,
        max_length=2048,
        default=None,
    )

    space: Space | None = Field(
        description=("CDF space to which data model is suppose to be stored under"),
        default=None,
    )

    externalId: ExternalId | None = Field(
        description=("Data model external id when resolving rules as CDF data model"),
        default=None,
        min_length=1,
        max_length=255,
    )

    version: str | None = Field(
        description=("Data model version"),
        min_length=1,
        max_length=43,
        default=None,
    )

    name: str | None = Field(
        description=("Human readable name of the data model"),
        min_length=1,
        max_length=255,
        default=None,
    )

    description: Description | None = Field(
        description=("Description/definition of the data model"),
        default=None,
    )

    created: datetime | None = Field(
        description=("Date of the data model creation"),
        default=None,
    )

    updated: datetime | None = Field(
        description=("Date of the data model update"),
        default=None,
    )

    creator: str | list[str] | None = Field(
        description=("Creator(s) of the data model"),
        default=None,
    )

    contributor: str | list[str] | None = Field(
        description=("Contributor(s) of the data model"),
        default=None,
    )

    rights: str | None = Field(
        description=("Usage rights of the data model"),
        default=None,
    )

    license: str | None = Field(
        description=("License of the data model"),
        default=None,
    )

    def to_pandas(self) -> pd.Series:
        """Converts Metadata to pandas Series."""
        return pd.Series(self.model_dump())

    def _repr_html_(self) -> str:
        """Returns HTML representation of Metadata."""
        return self.to_pandas().to_frame("value")._repr_html_()  # type: ignore[operator]


class CoreRules(RuleModel):
    """
    Rules is a core concept in `neat`. This represents fusion of data model
    definitions and (optionally) the transformation rules used to transform the data/graph
    from the source representation to the target representation defined by the data model.
    The rules are defined in a Excel sheet and then parsed into a `Rules` object. The
    `Rules` object is then used to generate data model and the`RDF` graph made of data
    model instances.

    Args:
        metadata: Data model metadata
        classes: Classes defined in the data model
        properties: Class properties defined in the data model with accompanying transformation rules
                    to transform data from source to target representation
        prefixes: Prefixes used in the data model. Defaults to PREFIXES
        instances: Instances defined in the data model. Defaults to None
        validators_to_skip: List of validators to skip. Defaults to []
    """

    metadata: CoreMetadata


#     @property
#     def raw_tables(self) -> list[str]:
#         return list(
#                 for rule in self.properties.values()
#                 if rule.is_raw_lookup

#     @field_validator("instances", mode="before")
#     def none_as_empty_list(cls, value):
#         if value is None:

#     @field_validator("classes", mode="before")
#     def dict_to_classes_obj(cls, value: dict | Classes) -> Classes:
#         if not isinstance(value, dict):

#     @field_validator("properties", mode="before")
#     def dict_to_properties_obj(cls, value: dict | Properties) -> Properties:
#         if not isinstance(value, dict):

#     @model_validator(mode="after")
#     @skip_model_validator("validators_to_skip")
#     def update_prefix_version_entities(self) -> Self:

#         # update expected_value_types
#         for id_ in self.properties.keys():
#             # only update version of expected value type which are part of this data model
#             if (
#                 and self.properties[id_].expected_value_type.prefix == "undefined"
#             ):

#             if self.properties[id_].expected_value_type.prefix == "undefined":

#         # update container
#         for id_ in self.properties.keys():
#             # only update version of expected value type which are part of this data model
#             if (
#                 and cast(ContainerEntity, self.properties[id_].container).prefix == "undefined"
#             ):

#         # update parent classes
#         for id_ in self.classes.keys():
#             if self.classes[id_].parent_class:
#                 for parent_class in cast(list[ParentClass], self.classes[id_].parent_class):
#                     if parent_class.prefix == "undefined":
#                     if not parent_class.version:


#     @model_validator(mode="after")
#     @skip_model_validator("validators_to_skip")
#     def update_container_description_and_name(self):
#         for id_ in self.properties.keys():
#             if (
#                 and self.properties[id_].container.external_id in self.classes
#                 and self.properties[id_].container.space == self.metadata.space
#             ):
#                 self.properties[id_].container.description = self.classes[
#                 ].description

#                 self.properties[id_].container.name = self.classes[
#                 ].class_name

#     @model_validator(mode="after")
#     @skip_model_validator("validators_to_skip")
#     def add_missing_classes(self):
#         for property_ in self.properties.values():
#             if property_.class_id not in self.classes:
#                 self.classes[property_.class_id] = Class(

#     def update_prefix(self, prefix: str):
#         if prefix == self.metadata.prefix:

#             # update entity ids for expected_value_types and containers
#             for id_ in self.properties.keys():
#                 if self.properties[id_].expected_value_type.prefix == old_prefix:

#                 if (
#                     and cast(ContainerEntity, self.properties[id_].container).prefix == old_prefix
#                 ):

#             # update parent classes
#             for id_ in self.classes.keys():
#                 if self.classes[id_].parent_class:
#                     for parent_class in cast(list[ParentClass], self.classes[id_].parent_class):
#                         if parent_class.prefix == old_prefix:

#             # update prefixes

#     def update_space(self, space: str):
#         "Convenience method for updating prefix more intuitive to CDF users"

#     def update_version(self, version: str):
#         if version == self.metadata.version:
#             for id_ in self.properties.keys():
#                 if (
#                     and self.properties[id_].expected_value_type.version == old_version
#                 ):

#             for id_ in self.classes.keys():
#                 if self.classes[id_].parent_class:
#                     for parent_class in cast(list[ParentClass], self.classes[id_].parent_class):
#                         if parent_class.prefix == self.metadata.prefix and parent_class.version == old_version:

#     @validator("prefixes")
#     @skip_field_validator("validators_to_skip")
#     def are_prefixes_compliant(cls, value, values):
#         if ill_formed_prefixes := [
#             prefix for prefix, _ in value.items() if re.search(more_than_one_none_alphanumerics_regex, prefix)
#         ]:
#             raise exceptions.MoreThanOneNonAlphanumericCharacter(
#             ).to_pydantic_custom_error()
#         if ill_formed_prefixes := [
#             prefix for prefix, _ in value.items() if not re.match(prefix_compliance_regex, prefix)
#         ]:
#             raise exceptions.PrefixesRegexViolation(
#                 ill_formed_prefixes, prefix_compliance_regex
#             ).to_pydantic_custom_error()

#     @validator("prefixes")
#     @skip_field_validator("validators_to_skip")
#     def are_namespaces_compliant(cls, value, values):
#         for _, namespace in value.items():

#         if ill_formed_namespaces:

#     @validator("prefixes")
#     @skip_field_validator("validators_to_skip")
#     def add_data_model_prefix_namespace(cls, value, values):
#         if "metadata" not in values:
#         if "prefix" not in values["metadata"].dict():
#             raise exceptions.FiledInMetadataSheetMissingOrFailedValidation(
#             ).to_pydantic_custom_error()
#         if "namespace" not in values["metadata"].dict():
#             raise exceptions.FiledInMetadataSheetMissingOrFailedValidation(
#             ).to_pydantic_custom_error()


#     @property
#     def space(self) -> str:
#         """Returns data model space."""

#     @property
#     def external_id(self) -> str:
#         """Returns data model external."""

#     @property
#     def name(self) -> str:
#         """Returns data model name."""

#     def _repr_html_(self) -> str:
#         """Pretty display of the TransformationRules object in a Notebook"""
#         for key in ["creator", "contributor"]:


# class Resource(RuleModel):
#     """
#     Base class for resources that constitute data model (i.e., classes, properties)

#     Args:
#         description: The description of the resource.
#         cdf_resource_type: The CDF resource type to which resource resolves to
#         deprecated: Whether the resource is deprecated or not.
#         deprecation_date: The date when the resource was deprecated.
#         replaced_by: The resource that replaced this resource.
#         source: Source of information for given resource
#         source_entity_name: The name of the source entity that is closest to the resource being described.
#         match_type: The match type of the resource being described and the source entity.
#         comment: Additional comment about mapping between the resource being described and the source entity.

#     """

#     # Solution model

#     # Solution CDF resource, it is not needed when working with FDM, this is only for
#     # Classic CDF data model

#     # Advance data modeling: Keeping track if Resource got deprecated or not
#     # Todo: Remove. Not used, only added as placeholder for future use.

#     # Advance data modeling: Relation to existing resources for purpose of mapping
#     source: HttpUrl | None = Field(
#         ),
#     source_entity_name: str | None = Field(
#     match_type: str | None = Field(

#     @model_validator(mode="before")
#     def replace_float_nan_with_default(cls, values: dict) -> dict:


# class ResourceDict(BaseModel, Generic[T_Resource]):

#     def __getitem__(self, item: str) -> T_Resource:

#     def __setitem__(self, key: str, value: T_Resource):

#     def __contains__(self, item: str) -> bool:

#     def __len__(self) -> int:

#     def __iter__(self) -> Iterator[str]:  # type: ignore[override]

#     def values(self) -> ValuesView[T_Resource]:

#     def keys(self) -> KeysView[str]:

#     def items(self) -> ItemsView[str, T_Resource]:

#     def to_pandas(self, drop_na_columns: bool = True, include: list[str] | None = None) -> pd.DataFrame:
#         """Converts ResourceDict to pandas DataFrame."""
#         if drop_na_columns:
#         if include is not None:

#     def groupby(self, by: str) -> dict[str, ResourceDict[T_Resource]]:
#         for key, resource in self.data.items():
#             if value not in groups:

#     def _repr_html_(self) -> str:
#         """Returns HTML representation of ResourceDict."""


# class Class(Resource):
#     """
#     Base class for all classes that are part of the data model.

#     Args:
#         class_id: The class ID of the class.
#         class_name: The name of the class.
#         parent_class: The parent class of the class.
#     """

#     # Solution model
#     # Used for hierarchical data modeling, and inheritance/extension of CDF data model
#     # Todo: Remove? Does not seem to be used anywhere.
#     #  This is for CDF solution architecht setting view.filter in data modeling.

#     @model_validator(mode="before")
#     def replace_nan_floats_with_default(cls, values: dict) -> dict:

#     @validator("class_id", always=True)
#     @skip_field_validator("validators_to_skip")
#     def is_class_id_compliant(cls, value, values):
#         if re.search(more_than_one_none_alphanumerics_regex, value):
#         if not re.match(class_id_compliance_regex, value):
#             raise exceptions.ClassSheetClassIDRegexViolation(
#                 value, class_id_compliance_regex
#             ).to_pydantic_custom_error()

#     @validator("class_name", always=True)
#     def set_class_name_if_none(cls, value, values):
#         if value is None:
#             if "class_id" not in values:
#             warnings.warn(

#     @field_validator("parent_class", mode="before")
#     @skip_field_validator("validators_to_skip")
#     def parent_class_to_list_of_entities(cls, value, values):
#         if isinstance(value, str) and value:
#             for v in value.replace(", ", ",").split(","):
#                 if ENTITY_ID_REGEX_COMPILED.match(v) or VERSIONED_ENTITY_REGEX_COMPILED.match(v):
#                     # if all fails defaults "neat" object which ends up being updated to proper
#                     # prefix and version upon completion of Rules validation


#     @field_validator("parent_class", mode="after")
#     @skip_field_validator("validators_to_skip")
#     def is_parent_class_id_compliant(cls, value, values):
#         if isinstance(value, list):
#             if illegal_ids := [v for v in value if re.search(more_than_one_none_alphanumerics_regex, v.suffix)]:
#                 raise exceptions.MoreThanOneNonAlphanumericCharacter(
#                 ).to_pydantic_custom_error()
#             if illegal_ids := [v for v in value if not re.match(class_id_compliance_regex, v.suffix)]:
#                 for v in illegal_ids:
#                 raise exceptions.ClassSheetParentClassIDRegexViolation(
#                     illegal_ids, class_id_compliance_regex
#                 ).to_pydantic_custom_error()


# class Classes(ResourceDict[Class]):
#     """This represents a collection of classes that are part of the data model."""

#     ...


# class Property(Resource):
#     """
#     A property is a characteristic of a class. It is a named attribute of a class that describes a range of values
#     or a relationship to another class.

#     Args:
#         class_id: Class ID to which property belongs
#         property_id: Property ID of the property
#         property_name: Property name. Defaults to property_id
#         expected_value_type: Expected value type of the property
#         min_count: Minimum count of the property values. Defaults to 0
#         max_count: Maximum count of the property values. Defaults to None
#         default: Default value of the property
#         property_type: Property type (DatatypeProperty/attribute or ObjectProperty/edge/relationship)
#         cdf_resource_type: CDF resource to under which property will be resolved to (e.g., Asset)
#         resource_type_property: To what property of CDF resource given property resolves to (e.g., Asset name)
#         source_type: In case if property resolves as CDF relationship, this argument indicates
#                      relationship source type (defaults to Asset)
#         target_type: In case if property resolves as CDF relationship, this argument
#                      indicates relationship target type (defaults to Asset)
#         label: CDF Label used for relationship. Defaults to property_id
#         relationship_external_id_rule: Rule to use when generating CDF relationship externalId
#         rule_type: Rule type for the transformation from source to target representation
#                    of knowledge graph. Defaults to None (no transformation)
#         rule: Actual rule for the transformation from source to target representation of
#               knowledge graph. Defaults to None (no transformation)
#         skip_rule: Flag indicating if rule should be skipped when performing
#                    knowledge graph transformations. Defaults to False

#     """

#     # Solution model

#     # OWL property

#     # Core CDF resources (Asset, Relationship, and Labels)
#     resource_type_property: list[str] | None = Field(
#         "example f cdf_resource_type is 'Asset', then this could"
#         "be 'name' or 'description'. Note you can specify "
#         "this property twice in CDF, once as 'name' and once as 'metadata",
#     # Specialization of cdf_resource_type to allow definition of both
#     # Asset and Relationship at the same time
#     cdf_resource_type: list[str] = Field(

#     # Transformation rule (domain to solution)
#     rule: str | AllReferences | SingleProperty | Hop | RawLookup | SPARQLQuery | Traversal | None = Field(

#     # Container specific things, only used for advance modeling or auto-filled by neat

#     @property
#     def is_raw_lookup(self) -> bool:

#     @model_validator(mode="before")
#     def replace_float_nan_with_default(cls, values: dict) -> dict:

#     @field_validator("container", mode="before")
#     def container_string_to_entity(cls, value):
#         if not value:

#         if ENTITY_ID_REGEX_COMPILED.match(value) or VERSIONED_ENTITY_REGEX_COMPILED.match(value):

#     @field_validator("expected_value_type", mode="before")
#     def expected_value_type_string_to_entity(cls, value):
#         # handle simple types
#         if value in XSD_VALUE_TYPE_MAPPINGS.keys():

#         # complex types correspond to relations to other classes
#         if ENTITY_ID_REGEX_COMPILED.match(value) or VERSIONED_ENTITY_REGEX_COMPILED.match(value):
#             return ValueType(
#         #     return ValueType(

#     @validator("class_id", always=True)
#     @skip_field_validator("validators_to_skip")
#     def is_class_id_compliant(cls, value, values):
#         if re.search(more_than_one_none_alphanumerics_regex, value):
#         if not re.match(class_id_compliance_regex, value):
#             raise exceptions.PropertiesSheetClassIDRegexViolation(
#                 value, class_id_compliance_regex
#             ).to_pydantic_custom_error()

#     @validator("property_id", always=True)
#     @skip_field_validator("validators_to_skip")
#     def is_property_id_compliant(cls, value, values):
#         if re.search(more_than_one_none_alphanumerics_regex, value):
#         if not re.match(property_id_compliance_regex, value):

#     @validator("expected_value_type", always=True)
#     @skip_field_validator("validators_to_skip")
#     def is_expected_value_type_compliant(cls, value, values):
#         if re.search(more_than_one_none_alphanumerics_regex, value.suffix):
#             raise exceptions.MoreThanOneNonAlphanumericCharacter(
#                 "expected_value_type", value
#             ).to_pydantic_custom_error()
#         if not re.match(class_id_compliance_regex, value.suffix):

#     @validator("rule_type", pre=True)
#     def to_lowercase(cls, value):

#     @validator("skip_rule", pre=True)
#     def from_string(cls, value):
#         if isinstance(value, str):

#     @validator("rule")
#     @skip_field_validator("validators_to_skip")
#     def is_valid_rule(cls, value, values):
#         if rule_type := values.get("rule_type"):
#             if not value:
#                 raise exceptions.RuleTypeProvidedButRuleMissing(
#                 ).to_pydantic_custom_error()

#     @validator("resource_type_property", pre=True)
#     def split_str(cls, v):
#         if v:

#     @field_validator("cdf_resource_type", mode="before")
#     def to_list_if_comma(cls, value, info):
#         if isinstance(value, str):
#             if value:
#             if cls.model_fields[info.field_name].default is None:

#     # Setters
#     # TODO: configure setters to only run if field_validators are successful, otherwise do not run them!
#     @property
#     def is_mandatory(self) -> bool:

#     @model_validator(mode="after")
#     def set_property_type(self):
#         if self.expected_value_type.type_ == EntityTypes.data_value_type:

#     @model_validator(mode="after")
#     def set_container_if_missing(self):
#         if not self.container and (
#         ):

#     @model_validator(mode="after")
#     def set_container_property_if_missing(self):
#         if not self.container_property and (
#         ):

#     @model_validator(mode="after")
#     def set_property_name_if_none(self):
#         if self.property_name is None:
#             warnings.warn(

#     @model_validator(mode="after")
#     @skip_model_validator("validators_to_skip")
#     def set_relationship_label(self):
#         if self.label is None:
#             warnings.warn(

#     @model_validator(mode="after")
#     @skip_model_validator("validators_to_skip")
#     def set_skip_rule(self):
#         if self.rule_type is None:
#             warnings.warn(

#     @model_validator(mode="after")
#     def set_default_as_list(self):
#         if (
#             and self.default
#             and self.max_count
#             and self.max_count != 1
#             and not isinstance(self.default, list)
#         ):
#             warnings.warn(
#             if isinstance(self.default, str):
#                 if self.default:

#     @model_validator(mode="after")
#     @skip_model_validator("validators_to_skip")
#     def is_default_value_type_proper(self):
#         if self.property_type == "DatatypeProperty" and self.default:

#             if type(default_value) != self.expected_value_type.python:
#                     if isinstance(self.default, list):
#                         for value in self.default:

#                     exceptions.DefaultValueTypeNotProper(
#                         self.property_id,
#                         self.expected_value_type.python,


# class Properties(ResourceDict[Property]):
#     """This represents a collection of properties that are part of the data model."""

#     ...


# class Prefixes(RuleModel):
#     """
#     Class deals with prefixes used in the data model and data model instances

#     Args:
#         prefixes: Dict of prefixes
#     """


# class Instance(RuleModel):
#     """
#     Class deals with RDF triple that defines data model instances of data, represented
#     as a single row in the `Instances` sheet of the Excel file.

#     Args:
#         instance: URI of the instance
#         property_: URI of the property
#         value: value of the property
#         namespace: namespace of the instance
#         prefixes: prefixes of the instance

#     !!! note "Warning"
#         Use of the `Instances` sheet is not recommended, instead if you need additional
#         triples in your graph use Graph Capturing Sheet instead!

#         See
#         [`extract_graph_from_sheet`](../graph/extractors.md#cognite.neat.graph.extractors.extract_graph_from_sheet)
#         for more details.
#     """


#     @staticmethod
#     def get_value(value, prefixes) -> URIRef | Literal:

#     @model_validator(mode="before")
#     def convert_values(cls, values: dict):
#         # we expect to read Excel sheet which contains naming convention of column
#         # 'Instance', 'Property', 'Value', if that's not the case we should raise error
#         if not {"Instance", "Property", "Value"}.issubset(set(values.keys())):


#         values["Instance"] = (

#         values["Property"] = (

#         if isinstance(values["Value"], str):
#             if not isinstance(values["Value"], URIRef):
#                     XSD.integer
#                     if cls.isint(values["Value"])
#                     else XSD.float
#                     if cls.isfloat(values["Value"])
#                     else XSD.string


#     @staticmethod
#     def isfloat(x):

#     @staticmethod
#     def isint(x):
