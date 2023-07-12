from __future__ import annotations

import logging
import math
import re
import warnings
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Dict, List, Optional

import pandas as pd
from graphql import GraphQLBoolean, GraphQLFloat, GraphQLInt, GraphQLString
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    ValidationError,
    constr,
    field_validator,
    model_validator,
    parse_obj_as,
    validator,
)
from pydantic.fields import FieldInfo
from rdflib import XSD, Literal, Namespace, URIRef

from cognite.neat.core.configuration import PREFIXES

from . import _exceptions
from .to_rdf_path import Entity, RuleType, parse_rule

__all__ = ["Class", "Instance", "Metadata", "Prefixes", "Property", "Resource", "TransformationRules"]

# mapping of XSD types to Python and GraphQL types
DATA_TYPE_MAPPING = {
    "boolean": {"python": "bool", "GraphQL": GraphQLBoolean},
    "float": {"python": "float", "GraphQL": GraphQLFloat},
    "integer": {"python": "int", "GraphQL": GraphQLInt},
    "nonPositiveInteger": {"python": "int", "GraphQL": GraphQLInt},
    "nonNegativeInteger": {"python": "int", "GraphQL": GraphQLInt},
    "negativeInteger": {"python": "int", "GraphQL": GraphQLInt},
    "long": {"python": "int", "GraphQL": GraphQLInt},
    "string": {"python": "str", "GraphQL": GraphQLString},
    "anyURI": {"python": "str", "GraphQL": GraphQLString},
    "normalizedString": {"python": "str", "GraphQL": GraphQLString},
    "token": {"python": "str", "GraphQL": GraphQLString},
    # Graphql does not have a datetime type this is CDF specific
    "dateTime": {"python": "datetime", "GraphQL": "Timestamp"},
}
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


class RuleModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, arbitrary_types_allowed=True, strict=False
    )


class URL(BaseModel):
    url: HttpUrl


Description = constr(min_length=1, max_length=255)

# regex expressions for compliance of Metadata sheet parsing
prefix_compliance_regex = r"^([a-zA-Z]+[a-zA-Z0-9]*[_-]{0,1}[a-zA-Z0-9]+)+$"
cdf_space_name_compliance_regex = rf"(?!^(space|cdf|dms|pg3|shared|system|node|edge)$)({prefix_compliance_regex})"
data_model_name_compliance_regex = r"^([a-zA-Z]+[a-zA-Z0-9]*[_]{0,1}[a-zA-Z0-9])+$"
version_compliance_regex = r"^([0-9]+[_-]{1}[0-9]+[_-]{1}[0-9]+[_-]{1}[a-zA-Z0-9]+)|([0-9]+[_-]{1}[0-9]+[_-]{1}[0-9]+)|([0-9]+[_-]{1}[0-9])|([0-9]+)$"

Prefix = constr(min_length=1, max_length=43)
ExternalId = constr(min_length=1, max_length=255)


class Metadata(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, arbitrary_types_allowed=True
    )
    prefix: Prefix = Field(
        alias="shortName",
        description="This is used as prefix for generation of RDF OWL/SHACL data model representation",
    )
    cdf_space_name: Prefix = Field(
        description="This is used as CDF space name to which model is intend to be stored. By default it is set to 'playground'",
        alias="cdfSpaceName",
        default="playground",
    )

    namespace: Optional[Namespace] = Field(
        description="This is used as RDF namespace for generation of RDF OWL/SHACL data model representation and/or for generation of RDF graphs",
        min_length=1,
        max_length=2048,
        default=None,
    )
    data_model_name: Optional[ExternalId] = Field(
        description="Name that uniquely identifies data model",
        alias="dataModelName",
        default=None,
    )

    version: str = Field(
        min_length=1,
        max_length=43,
    )
    is_current_version: bool = Field(alias="isCurrentVersion", default=True)
    created: datetime
    updated: datetime = Field(default_factory=lambda: datetime.utcnow())
    title: str = Field(min_length=1, max_length=255)
    description: Description
    creator: str | list[str]
    contributor: Optional[str | list[str]] = None
    rights: Optional[str] = "Restricted for Internal Use of Cognite"
    externalIdPrefix: Optional[str] = Field(alias="externalIdPrefix", default=None)
    data_set_id: Optional[int] = Field(alias="dataSetId", default=None)
    imports: Optional[list[str]] = Field(
        description="Placeholder in case when data model is modular, i.e. provided as set of Excel files",
        default=None,
    )
    source: Optional[str | Path] = Field(
        description="File path to Excel file which was used to produce Transformation Rules",
        default=None,
    )
    issues: Optional[List[str]] = Field(default=None, description="Storing list of pydantic validation issues")
    valid: Optional[bool] = Field(default=True, description="Indicates whether resource is valid or not")

    @field_validator(
        "externalIdPrefix",
        "contributor",
        "contributor",
        "description",
        "rights",
        mode="before",
    )
    def replace_float_nan_with_default(cls, value, info):
        if isinstance(value, float) and math.isnan(value):
            return cls.model_fields[info.field_name].default
        return value

    @validator("prefix", always=True)
    def is_prefix_compliant(cls, value):
        if not re.match(prefix_compliance_regex, value):
            raise _exceptions.Error100(value, prefix_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("cdf_space_name", always=True)
    def is_cdf_space_name_compliant(cls, value):
        if not re.match(cdf_space_name_compliance_regex, value):
            raise _exceptions.Error101(value, cdf_space_name_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("namespace", always=True)
    def set_namespace_if_none(cls, value, values):
        if value is None:
            if values["cdf_space_name"] == "playground":
                return Namespace(f"http://purl.org/cognite/{values['prefix']}#")
            else:
                return Namespace(f"http://purl.org/cognite/{values['cdf_space_name']}/{values['prefix']}#")
        try:
            return Namespace(parse_obj_as(HttpUrl, value))
        except ValidationError:
            raise _exceptions.Error102(value).to_pydantic_custom_error()

    @validator("namespace", always=True)
    def fix_namespace_ending(cls, value):
        if value.endswith("#") or value.endswith("/"):
            return value
        warnings.warn(_exceptions.Warning100(value).message, stacklevel=2)
        return f"{value}#"

    @validator("data_model_name", always=True)
    def set_data_model_name_if_none(cls, value, values):
        if value is not None:
            return value
        warnings.warn(_exceptions.Warning101(values["prefix"].replace("-", "_")).message, stacklevel=2)
        return values["prefix"].replace("-", "_")

    @validator("data_model_name", always=True)
    def is_data_model_name_compliant(cls, value):
        if not re.match(data_model_name_compliance_regex, value):
            raise _exceptions.Error103(value, data_model_name_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("version", always=True)
    def is_version_compliant(cls, value):
        # turn "." into "_" to avoid issues with CDF
        if "." in value:
            warnings.warn(_exceptions.Warning102().message, stacklevel=2)
            value = value.replace(".", "_")
        if not re.match(version_compliance_regex, value):
            raise _exceptions.Error104(value, version_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @field_validator("creator", "contributor", mode="before")
    def to_list_if_comma(cls, value, info):
        if isinstance(value, str):
            if value:
                return value.replace(", ", ",").split(",")
            if cls.model_fields[info.field_name].default is None:
                return None
        return value


class Resource(RuleModel):
    # Solution model
    description: Optional[Description] = Field(alias="Description", default=None)

    # Solution CDF resource, it is not needed when working with FDM, this is only for
    # Classic CDF data model
    cdf_resource_type: Optional[str] = Field(alias="Resource Type", default=None)

    # Advance data modeling: Keeping track if Resource got deprecated or not
    deprecated: bool = Field(default=False)
    deprecation_date: Optional[datetime] = Field(alias="deprecationDate", default=None)
    replaced_by: Optional[str] = Field(alias="replacedBy", default=None)

    # Advance data modeling: Relation to existing resources for purpose of mapping
    source: Optional[HttpUrl] = Field(
        alias="Source", description="Source of information for given entity, e.g. CIM", default=None
    )
    source_entity_name: Optional[str] = Field(
        alias="Source Entity Name", description="Closest entity in source, e.g. Substation", default=None
    )
    match_type: Optional[str] = Field(
        alias="Match Type", description="Type of match between source entity and one being defined", default=None
    )
    comment: Optional[str] = Field(alias="Comment", description="Comment about mapping", default=None)
    issues: Optional[List[str]] = Field(default=None, description="Storing list of pydantic validation issues")
    valid: Optional[bool] = Field(default=True, description="Indicates whether resource is valid or not")

    @model_validator(mode="before")
    def replace_float_nan_with_default(cls, values: dict) -> dict:
        return replace_nan_floats_with_default(values, cls.model_fields)


class_id_compliance_regex = r"^([a-zA-Z]+[a-zA-Z0-9]+[._-]{0,1}[a-zA-Z0-9]+)+$"


class Class(Resource):
    class_id: ExternalId = Field(
        alias="Class",
    )
    class_name: Optional[ExternalId] = Field(alias="Name", default=None)
    # Solution model
    parent_class: Optional[ExternalId] = Field(alias="Parent Class", default=None)

    # Solution CDF resource
    parent_asset: Optional[ExternalId] = Field(alias="Parent Asset", default=None)

    @model_validator(mode="before")
    def replace_nan_floats_with_default(cls, values: dict) -> dict:
        return replace_nan_floats_with_default(values, cls.model_fields)

    @validator("class_id", always=True)
    def is_class_id_compliant(cls, value):
        if not re.match(class_id_compliance_regex, value):
            raise _exceptions.Error200(value, class_id_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("class_name", always=True)
    def set_class_name_if_none(cls, value, values):
        if value is None:
            if "class_id" not in values:
                raise _exceptions.Error201().to_pydantic_custom_error()
            warnings.warn(_exceptions.Warning200(values["class_id"]).message, stacklevel=2)
            value = values["class_id"]
        return value


property_id_compliance_regex = r"^(\*)|(([a-zA-Z]+[a-zA-Z0-9]+[._-]{0,1}[a-zA-Z0-9]+)+)$"


class Property(Resource):
    # Solution model
    class_id: ExternalId = Field(alias="Class")
    property_id: ExternalId = Field(alias="Property")
    property_name: Optional[ExternalId] = Field(alias="Name", default=None)
    expected_value_type: ExternalId = Field(alias="Type")
    min_count: Optional[int] = Field(alias="Min Count", default=0)
    max_count: Optional[int] = Field(alias="Max Count", default=None)

    # OWL property
    property_type: str = "DatatypeProperty"

    # Solution CDF resource
    resource_type_property: Optional[list[str]] = Field(alias="Resource Type Property", default=None)
    source_type: str = Field(alias="Relationship Source Type", default="Asset")
    target_type: str = Field(alias="Relationship Target Type", default="Asset")
    label: Optional[str] = Field(alias="Relationship Label", default=None)
    relationship_external_id_rule: Optional[str] = Field(alias="Relationship ExternalID Rule", default=None)

    # Transformation rule (domain to solution)
    rule_type: RuleType = Field(alias="Rule Type", default=None)
    rule: Optional[str] = Field(alias="Rule", default=None)
    skip_rule: bool = Field(alias="Skip", default=False)

    # Specialization of cdf_resource_type to allow definition of both
    # Asset and Relationship at the same time
    cdf_resource_type: list[str] = Field(alias="Resource Type", default=[])

    @property
    def is_raw_lookup(self) -> bool:
        return self.rule_type == RuleType.rawlookup

    @model_validator(mode="before")
    def replace_float_nan_with_default(cls, values: dict) -> dict:
        return replace_nan_floats_with_default(values, cls.model_fields)

    @validator("class_id", always=True)
    def is_class_id_compliant(cls, value):
        if not re.match(class_id_compliance_regex, value):
            raise _exceptions.Error300(value, class_id_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("property_id", always=True)
    def is_property_id_compliant(cls, value):
        if not re.match(property_id_compliance_regex, value):
            raise _exceptions.Error301(value, property_id_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("expected_value_type", always=True)
    def is_expected_value_type_compliant(cls, value):
        if not re.match(class_id_compliance_regex, value):
            raise _exceptions.Error302(value, class_id_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("rule_type", pre=True)
    def to_lowercase(cls, value):
        return value.casefold() if value else value

    @validator("skip_rule", pre=True)
    def from_string(cls, value):
        if isinstance(value, str):
            return value.casefold() in {"true", "skip", "yes", "y"}
        return value

    @validator("rule")
    def is_valid_rule(cls, value, values):
        if rule_type := values.get("rule_type"):
            _ = parse_rule(value, rule_type)
        return value

    @validator("resource_type_property", pre=True)
    def split_str(cls, v):
        if v:
            return [v.strip() for v in v.split(",")] if "," in v else [v]

    @field_validator("cdf_resource_type", mode="before")
    def to_list_if_comma(cls, value, info):
        if isinstance(value, str):
            if value:
                return value.replace(", ", ",").split(",")
            if cls.model_fields[info.field_name].default is None:
                return None
        return value

    @model_validator(mode="after")
    def set_property_type(cls, model: "Property"):
        if model.expected_value_type in DATA_TYPE_MAPPING.keys():
            model.property_type = "DatatypeProperty"
        else:
            model.property_type = "ObjectProperty"
        return model

    @model_validator(mode="after")
    def set_property_name_if_none(cls, model: "Property"):
        if model.property_name is None:
            warnings.warn(_exceptions.Warning300(model.property_id).message, stacklevel=2)
            model.property_name = model.property_id
        return model

    @model_validator(mode="after")
    def set_relationship_label(cls, model: "Property"):
        if model.label is None:
            warnings.warn(_exceptions.Warning301(model.property_id).message, stacklevel=2)
            model.label = model.property_id
        return model

    # TODO: witch to model_validator that runs after all validators are done
    # as this one runs as setter and is not aware of the changes made by other validators
    @validator("skip_rule", pre=True, always=True)
    def no_rule(cls, value, values):
        return True if values.get("rule_type") is None else value


class Prefixes(RuleModel):
    prefixes: Dict[str, Namespace] = PREFIXES


class Instance(RuleModel):
    """Class deals with instances of classes in the data model"""

    instance: Optional[URIRef] = Field(alias="Instance", default=None)
    property_: Optional[URIRef] = Field(alias="Property", default=None)
    value: Optional[Literal | URIRef] = Field(alias="Value", default=None)
    namespace: Namespace
    prefixes: Dict[str, Namespace]

    @staticmethod
    def get_value(value, prefixes) -> URIRef | Literal:
        try:
            url = URL(url=value).url
            return URIRef(url)
        except ValidationError:
            try:
                entity = Entity.from_string(value)
                return URIRef(prefixes[entity.prefix][entity.name])
            except ValueError:
                return value

    @model_validator(mode="before")
    def convert_values(cls, values: dict):
        # we expect to read Excel sheet which contains naming convention of column
        # 'Instance', 'Property', 'Value', if that's not the case we should raise error
        if not {"Instance", "Property", "Value"}.issubset(set(values.keys())):
            raise TypeError("We only support inputs from the transformation rule Excel sheet!!!")

        namespace = values["namespace"]
        prefixes = values["prefixes"]

        values["Instance"] = cls.get_value(values["Instance"], prefixes)
        values["Instance"] = (
            values["Instance"] if isinstance(values["Instance"], URIRef) else URIRef(namespace[values["Instance"]])
        )

        values["Property"] = cls.get_value(values["Property"], prefixes)
        values["Property"] = (
            values["Property"] if isinstance(values["Property"], URIRef) else URIRef(namespace[values["Property"]])
        )

        if isinstance(values["Value"], str):
            values["Value"] = cls.get_value(values["Value"], prefixes)
            if not isinstance(values["Value"], URIRef):
                datatype = (
                    XSD.integer
                    if cls.isint(values["Value"])
                    else XSD.float
                    if cls.isfloat(values["Value"])
                    else XSD.string
                )
                values["Value"] = Literal(values["Value"], datatype=datatype)
        elif isinstance(values["Value"], float):
            values["Value"] = Literal(values["Value"], datatype=XSD.float)
        elif isinstance(values["Value"], int):
            values["Value"] = Literal(values["Value"], datatype=XSD.integer)
        elif isinstance(values["Value"], bool):
            values["Value"] = Literal(values["Value"], datatype=XSD.boolean)
        elif isinstance(values["Value"], datetime):
            values["Value"] = Literal(values["Value"], datatype=XSD.dateTime)
        else:
            values["Value"] = Literal(values["Value"], datatype=XSD.string)

        return values

    @staticmethod
    def isfloat(x):
        try:
            _ = float(x)
        except (TypeError, ValueError):
            return False
        else:
            return True

    @staticmethod
    def isint(x):
        try:
            a = float(x)
            b = int(a)
        except (TypeError, ValueError):
            return False
        else:
            return a == b


class TransformationRules(RuleModel):
    metadata: Metadata
    classes: dict[str, Class]
    properties: dict[str, Property]
    prefixes: Optional[dict[str, Namespace]] = PREFIXES
    instances: Optional[list[Instance]] = None

    @property
    def raw_tables(self) -> list[str]:
        return list(
            {
                parse_rule(rule.rule, RuleType.rawlookup).table.name
                for rule in self.properties.values()
                if rule.is_raw_lookup
            }
        )

    @validator("properties", each_item=True)
    def class_property_exist(cls, value, values):
        if classes := values.get("classes"):
            if value.class_id not in classes:
                raise _exceptions.Error600(value.property_id, value.class_id).to_pydantic_custom_error()
        return value

    @validator("properties", each_item=True)
    def value_type_exist(cls, value, values):
        if classes := values.get("classes"):
            if value.property_type == "ObjectProperty" and value.expected_value_type not in classes:
                raise _exceptions.Error603(
                    value.class_i, value.property_id, value.expected_value_type
                ).to_pydantic_custom_error()
        return value

    @validator("properties")
    def is_type_defined_as_object(cls, value):
        defined_objects = {property_.class_id for property_ in value.values()}

        if undefined_objects := [
            property_.expected_value_type
            for _, property_ in value.items()
            if property_.property_type == "ObjectProperty" and property_.expected_value_type not in defined_objects
        ]:
            raise _exceptions.Error604(undefined_objects).to_pydantic_custom_error()
        else:
            return value

    @validator("prefixes")
    def are_prefixes_compliant(cls, value):
        if ill_formed_prefixes := [
            prefix for prefix, _ in value.items() if not re.match(prefix_compliance_regex, prefix)
        ]:
            raise _exceptions.Error400(ill_formed_prefixes, prefix_compliance_regex).to_pydantic_custom_error()
        else:
            return value

    @validator("prefixes")
    def are_namespaces_compliant(cls, value):
        ill_formed_namespaces = []
        for _, namespace in value.items():
            try:
                _ = URL(url=namespace).url
            except ValueError:
                ill_formed_namespaces += namespace

        if ill_formed_namespaces:
            raise _exceptions.Error401(ill_formed_namespaces).to_pydantic_custom_error()
        else:
            return value

    @validator("prefixes")
    def add_data_model_prefix_namespace(cls, value, values):
        if "metadata" not in values:
            raise _exceptions.Error601().to_pydantic_custom_error()
        if "prefix" not in values["metadata"].dict():
            raise _exceptions.Error602(missing_field="prefix").to_pydantic_custom_error()
        if "namespace" not in values["metadata"].dict():
            raise _exceptions.Error602(missing_field="namespace").to_pydantic_custom_error()

        value[values["metadata"].prefix] = values["metadata"].namespace
        return value

    # Bunch of methods that work on top of this class we might move out of TransformationRules class
    def get_labels(self) -> set[str]:
        """Return CDF labels for classes and relationships."""
        class_labels = {class_.class_id for class_ in self.classes.values()}

        property_labels = {property_.property_id for property_ in self.properties.values()}

        relationship_labels = {
            rule.label for rule in self.properties.values() if "Relationship" in rule.cdf_resource_type
        }

        return class_labels.union(relationship_labels).union(property_labels)

    def get_defined_classes(self) -> set[str]:
        """Returns classes that have been defined in the data model."""
        return {property.class_id for property in self.properties.values()}

    def get_classes_with_properties(self) -> dict[str, list[Property]]:
        """Returns classes that have been defined in the data model."""
        # TODO: Do not particularly like method name, find something more suitable
        class_property_pairs = {}

        for property_ in self.properties.values():
            class_ = property_.class_id
            if class_ in class_property_pairs:
                class_property_pairs[class_] += [property_]
            else:
                class_property_pairs[class_] = [property_]

        return class_property_pairs

    def get_class_property_pairs(self) -> dict[str, dict[str, Property]]:
        """This method will actually consider only the first definition of given property!"""
        class_property_pairs = {}

        for class_, properties in self.get_classes_with_properties().items():
            processed_properties = {}
            for property_ in properties:
                if property_.property_id in processed_properties:
                    warnings.warn(
                        "Property has been defined more than once! Only first definition will be considered.",
                        stacklevel=2,
                    )
                    continue
                processed_properties[property_.property_id] = property_
            class_property_pairs[class_] = processed_properties

        return class_property_pairs

    def check_data_model_definitions(self):
        """Check if data model definitions are valid."""
        issues = set()
        for class_, properties in self.get_classes_with_properties().items():
            analyzed_properties = []
            for property_ in properties:
                if property_.property_id not in analyzed_properties:
                    analyzed_properties.append(property_.property_id)
                else:
                    issues.add(f"Property {property_.property_id} of class {class_} has been defined more than once!")
        return issues

    def reduce_data_model(self, desired_classes: set, skip_validation: bool = False) -> TransformationRules:
        """Reduce the data model to only include desired classes and their properties.

        Parameters
        ----------
        desired_classes : set
            Desired classes to include in the reduced data model
        skip_validation : bool
            To skip underlying pydantic validation, by default False

        Returns
        -------
        TransformationRules
            Instance of TransformationRules

        Notes
        -----
        It is fine to skip validation since we are deriving the reduced data model from data
        model (i.e. TransformationRules) which has already been validated.
        """

        defined_classes = self.get_defined_classes()
        possible_classes = defined_classes.intersection(desired_classes)
        impossible_classes = desired_classes - possible_classes

        if not possible_classes:
            logging.error("None of the desired classes are defined in the data model!")
            raise ValueError("None of the desired classes are defined in the data model!")

        if impossible_classes:
            logging.warning(f"Could not find the following classes defined in the data model: {impossible_classes}")
            warnings.warn(
                f"Could not find the following classes defined in the data model: {impossible_classes}", stacklevel=2
            )

        reduced_data_model = {
            "metadata": self.metadata,
            "prefixes": self.prefixes,
            "classes": {},
            "properties": {},
            "instances": self.instances,
        }

        logging.info(f"Reducing data model to only include the following classes: {possible_classes}")
        for class_ in possible_classes:
            reduced_data_model["classes"][class_] = self.classes[class_]

        for id_, property_definition in self.properties.items():
            if property_definition.class_id in possible_classes:
                reduced_data_model["properties"][id_] = property_definition

        if skip_validation:
            return TransformationRules.construct(**reduced_data_model)
        else:
            return TransformationRules(**reduced_data_model)

    def to_dataframe(self) -> Dict[str, pd.DataFrame]:
        """Represent data model as a dictionary of data frames, where each data frame
        represents properties defined for a given class.

        Returns
        -------
        Dict[str, pd.DataFrame]
            Simplified representation of the data model
        """

        data_model = {}

        defined_classes = self.get_classes_with_properties()

        for class_ in defined_classes:
            properties = {}
            for property_ in defined_classes[class_]:
                if property_.property_id not in properties:
                    properties[property_.property_id] = {
                        "property_type": property_.property_type,
                        "value_type": property_.expected_value_type,
                        "min_count": property_.min_count,
                        "max_count": property_.max_count,
                    }

            data_model[class_] = pd.DataFrame(properties).T

        return data_model

    def get_class_linkage(self) -> pd.DataFrame:
        """Returns a dataframe with the class linkage of the data model."""

        class_linkage = pd.DataFrame(columns=["source_class", "target_class", "connecting_property", "max_occurrence"])
        for property_ in self.properties.values():
            if property_.property_type == "ObjectProperty":
                new_row = pd.Series(
                    {
                        "source_class": property_.class_id,
                        "target_class": property_.expected_value_type,
                        "connecting_property": property_.property_id,
                        "max_occurrence": property_.max_count,
                    }
                )
                class_linkage = pd.concat([class_linkage, new_row.to_frame().T], ignore_index=True)

        class_linkage.drop_duplicates(inplace=True)

        return class_linkage

    def get_connected_classes(self) -> set:
        """Return a set of classes that are connected to other classes."""
        class_linkage = self.get_class_linkage()
        return set(class_linkage.source_class.values).union(set(class_linkage.target_class.values))

    def get_disconnected_classes(self):
        """Return a set of classes that are disconnected (i.e. isolated) from other classes."""
        return self.get_defined_classes() - self.get_connected_classes()

    def get_symmetric_pairs(self) -> list:
        """Returns a list of pairs of symmetrically linked classes."""
        # TODO: Find better name for this method

        class_linkage = self.get_class_linkage()
        if class_linkage.empty:
            return []

        sym_pairs = set()
        for _, row in class_linkage.iterrows():
            source = row.source_class
            target = row.target_class
            target_targets = class_linkage[class_linkage.source_class == target].target_class.values
            if source in target_targets and (source, target) not in sym_pairs:
                sym_pairs.add((source, target))
        return sym_pairs

    def get_entity_names(self):
        class_names = set()
        property_names = set()
        for class_, properties in self.to_dataframe().items():
            class_names.add(class_)
            property_names = property_names.union(set(properties.index))
        return class_names.union(property_names)
