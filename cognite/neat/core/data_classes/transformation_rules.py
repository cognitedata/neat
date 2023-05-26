from __future__ import annotations

import logging
import math
import warnings
from datetime import datetime
from typing import Dict, List, Optional, Self, Union

import pandas as pd
from graphql import GraphQLBoolean, GraphQLFloat, GraphQLInt, GraphQLString
from pydantic import BaseModel, Field, HttpUrl, ValidationError, root_validator, validator
from rdflib import XSD, Literal, Namespace, URIRef

from cognite.neat.core.configuration import PREFIXES, Tables
from cognite.neat.core.data_classes.rules import Entity, RuleType, parse_rule

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
}
METADATA_VALUE_MAX_LENGTH = 5120


class URL(BaseModel):
    url: HttpUrl


class Resource(BaseModel):
    # Solution model
    class_name: str = Field(alias="Class")
    description: str = Field(alias="Description", default="")

    # Solution CDF resource
    cdf_resource_type: str = Field(alias="Resource Type")

    # Solution model advance configuration
    deprecated: bool = Field(default=False)
    deprecation_date: Optional[datetime] = Field(alias="deprecationDate", default=None)
    replaced_by: str = Field(alias="replacedBy", default=None)
    similar_to: HttpUrl = Field(alias="similarTo", default=None)
    similarity_score: float = Field(alias="similarityScore", default=None)
    equal_to: HttpUrl = Field(alias="equalTo", default=None)

    @validator(
        "deprecated",
        "deprecation_date",
        "replaced_by",
        "similar_to",
        "similarity_score",
        "equal_to",
        "description",
        pre=True,
    )
    def replace_float_nan_with_default(cls, value, field):
        if isinstance(value, float) and math.isnan(value):
            return field.default
        return value


class Class(Resource):
    # Solution model
    parent_class: str = Field(alias="Parent Class", default=None)

    # Solution CDF resource
    parent_asset: str = Field(alias="Parent Asset", default=None)

    @validator("parent_class", "parent_asset", pre=True)
    def replace_float_nan_with_default(cls, value, field):
        if isinstance(value, float) and math.isnan(value):
            return field.default
        return value


class Property(Resource):
    # Solution model
    property_name: str = Field(alias="Property")
    expected_value_type: str = Field(alias="Type")
    min_count: Optional[int] = Field(alias="Min Count", default=0)
    max_count: Optional[int] = Field(alias="Max Count", default=None)

    # OWL property
    property_type: str = "DatatypeProperty"

    # Solution CDF resource
    resource_type_property: List[str] = Field(alias="Resource Type Property", default=None)
    source_type: str = Field(alias="Relationship Source Type", default="Asset")
    target_type: str = Field(alias="Relationship Target Type", default="Asset")
    label: str = Field(alias="Relationship Label", default=None)
    relationship_external_id_rule: str = Field(alias="Relationship ExternalID Rule", default=None)

    # Transformation rule (domain to solution)
    rule_type: RuleType = Field(alias="Rule Type", default=None)
    rule: str = Field(alias="Rule", default=None)
    skip_rule: bool = Field(alias="Skip", default=False)

    # Specialization of cdf_resource_type to allow definition of both
    # Asset and Relationship at the same time
    cdf_resource_type: list[str] = Field(alias="Resource Type")

    @property
    def is_raw_lookup(self) -> bool:
        return self.rule_type == RuleType.rawlookup

    @validator(
        "max_count",
        "min_count",
        "target_type",
        "source_type",
        "label",
        "relationship_external_id_rule",
        "resource_type_property",
        "skip_rule",
        "rule",
        "rule_type",
        pre=True,
    )
    def replace_float_nan_with_default(cls, value, field):
        if isinstance(value, float) and math.isnan(value):
            return field.default
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

    @validator("label")
    def set_relationship_label(cls, value, values):
        if "Relationship" in values.get("cdf_resource_type") and not value:
            return values.get("property_name")
        return value

    @validator("cdf_resource_type", pre=True)
    def to_list_if_comma(cls, value, field):
        if isinstance(value, str):
            if value:
                return value.replace(", ", ",").split(",")
            if field.default is None:
                return None
        return value

    @validator("property_type", pre=True, always=True)
    def set_property_type(cls, value, values):
        if values["expected_value_type"] in DATA_TYPE_MAPPING.keys():
            return "DatatypeProperty"
        else:
            return "ObjectProperty"

    @validator("skip_rule", pre=True, always=True)
    def no_rule(cls, value, values):
        if values.get("rule_type") is None:
            return True
        else:
            return value


class Metadata(BaseModel):
    prefix: str = Field(alias="shortName")
    namespace: Namespace = None
    version: str
    isCurrentVersion: bool = True
    created: datetime
    updated: datetime = Field(default_factory=lambda: datetime.utcnow())
    title: str
    description: Optional[str] = None
    abstract: Optional[str] = None
    creator: str | list[str]
    contributor: Optional[str | list[str]] = None
    rights: Optional[str] = "Restricted for Internal Use of Cognite"
    externalIdPrefix: str = Field(alias="externalIdPrefix", default=None)
    data_set_id: int = Field(alias="dataSetId")

    @validator(
        "externalIdPrefix",
        "contributor",
        "contributor",
        "description",
        "rights",
        pre=True,
    )
    def replace_float_nan_with_default(cls, value, field):
        if isinstance(value, float) and math.isnan(value):
            return field.default
        return value

    @validator("namespace", always=True)
    def set_namespace(cls, value, values):
        if value is None:
            return Namespace(f"http://purl.org/cognite/{values['prefix']}#")

    @validator("creator", "contributor")
    def to_list_if_comma(cls, value, field):
        if isinstance(value, str):
            if value:
                return value.replace(", ", ",").split(",")
            if field.default is None:
                return None
        return value

    class Config:
        allow_population_by_field_name = True

    @classmethod
    def create_from_dataframe(cls, raw_dfs) -> Self:
        expected_tables = Tables.as_set()
        if missing_tables := (expected_tables - set(raw_dfs)):
            raise ValueError(f"Missing the following tables {', '.join(missing_tables)}")
        return Metadata(**dict(zip(raw_dfs[Tables.metadata][0], raw_dfs[Tables.metadata][1])))


class Prefixes(BaseModel):
    prefixes: Dict[str, Namespace] = PREFIXES

    @staticmethod
    def create_from_dataframe(raw_dfs: pd.DataFrame) -> dict[str, Namespace]:
        prefixes = {}
        for i, row in raw_dfs.iterrows():
            try:
                url = URL(url=row["URI"]).url
                prefixes[row["Prefix"]] = Namespace(url)
            except ValueError as e:
                msg = f"Prefix <{row['Prefix']}> has invalid URL: <{row['URI']}> fix this in Prefixes sheet at the row {i + 2} in the rule file!"
                logging.error(msg)
                raise ValueError(msg) from e

        return prefixes


class Instance(BaseModel):
    """Class deals with instances of classes in the data model"""

    instance: URIRef = Field(alias="Instance", default=None)
    property_: URIRef = Field(alias="Property", default=None)
    value: Union[Literal, URIRef] = Field(alias="Value", default=None)
    namespace: URIRef
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

    @root_validator(pre=True)
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

        values["Value"] = cls.get_value(values["Value"], prefixes)

        if not isinstance(values["Value"], URIRef):
            datatype = (
                XSD.integer if cls.isint(values["Value"]) else XSD.float if cls.isfloat(values["Value"]) else XSD.string
            )
            values["Value"] = Literal(values["Value"], datatype=datatype)

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


class TransformationRules(BaseModel):
    metadata: Metadata
    classes: dict[str, Class]
    properties: dict[str, Property]
    prefixes: dict[str, Namespace]
    instances: list[tuple] = None

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
    def is_valid_mapping(cls, value, values):
        if classes := values.get("classes"):
            if value.class_name not in classes:
                raise ValueError(f"invalid mapping rule, {value.class_name} does not exist ")
        return value

    @validator("properties", each_item=True)
    def value_type_exist(cls, value, values):
        if classes := values.get("classes"):
            if value.property_type == "ObjectProperty" and value.expected_value_type not in classes:
                msg = f"Property <{value.property_name}> defined for class <{value.class_name}> has "
                msg += f"value type <{value.expected_value_type}> which is not defined!"
                raise ValueError(msg)
        return value

    @validator("properties", each_item=True)
    def add_missing_label(cls, value):
        "Add label if missing for relationships"
        if value.label is None and "Relationship" in value.cdf_resource_type:
            value.label = value.property_name
        return value

    @validator("properties")
    def is_type_defined_as_object(cls, value):
        "Checks if property expected value type is defined as object"
        defined_objects = {property_.class_name for property_ in value.values()}

        if undefined_objects := [
            id
            for id, property_ in value.items()
            if property_.property_type == "ObjectProperty" and property_.expected_value_type not in defined_objects
        ]:
            msg = [
                f"\nProperty at {id} has type <{value[id].expected_value_type}> for which mapping is not defined!"
                for id in undefined_objects
            ]
            raise ValueError("".join(msg))
        return value

    @validator("properties", each_item=True)
    def class_property_exist(cls, value, values):
        if classes := values.get("classes"):
            if value.class_name not in classes:
                raise ValueError(
                    f"Property <{value.property_name}> defined for non-existing class <{value.class_name}>!"
                )
        return value

    @validator("prefixes")
    def add_data_model_prefix_namespace(cls, value, values):
        value[values["metadata"].prefix] = values["metadata"].namespace
        return value

    def get_labels(self) -> set[str]:
        """Return CDF labels for classes and relationships."""
        class_labels = {class_.class_name for class_ in self.classes.values()}

        property_labels = {property_.property_name for property_ in self.properties.values()}

        relationship_labels = {
            rule.label for rule in self.properties.values() if "Relationship" in rule.cdf_resource_type
        }

        return class_labels.union(relationship_labels).union(property_labels)

    def get_defined_classes(self) -> set[str]:
        """Returns classes that have been defined in the data model."""
        return {property.class_name for property in self.properties.values()}

    def get_classes_with_properties(self) -> dict[str, list[Property]]:
        """Returns classes that have been defined in the data model."""
        # TODO: Do not particularly like method name, find something more suitable
        class_property_pairs = {}

        for property_ in self.properties.values():
            class_ = property_.class_name
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
                if property_.property_name in processed_properties:
                    warnings.warn(
                        "Property has been defined more than once! Only first definition will be considered.",
                        stacklevel=2,
                    )
                    continue
                processed_properties[property_.property_name] = property_
            class_property_pairs[class_] = processed_properties

        return class_property_pairs

    def check_data_model_definitions(self):
        """Check if data model definitions are valid."""
        issues = set()
        for class_, properties in self.get_classes_with_properties().items():
            analyzed_properties = []
            for property in properties:
                if property.property_name not in analyzed_properties:
                    analyzed_properties.append(property.property_name)
                else:
                    issues.add(f"Property {property.property_name} of class {class_} has been defined more than once!")
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
            if property_definition.class_name in possible_classes:
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
                if property_.property_name not in properties:
                    properties[property_.property_name] = {
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
                        "source_class": property_.class_name,
                        "target_class": property_.expected_value_type,
                        "connecting_property": property_.property_name,
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

    def define_relationships(self, stop_on_exception: bool = False) -> RelationshipDefinitions:
        relationships = {}

        # Unique ids used to check for redefinitions of relationships
        ids = set()

        for row, rule in self.properties.items():
            if "Relationship" in rule.cdf_resource_type:
                relationship = RelationshipDefinition(
                    source_class=rule.class_name,
                    target_class=rule.expected_value_type,
                    property_=rule.property_name,
                    labels=list(
                        set([rule.label, rule.class_name, rule.expected_value_type, "non-historic", rule.property_name])
                    ),
                    target_type=rule.target_type,
                    source_type=rule.source_type,
                    relationship_external_id_rule=rule.relationship_external_id_rule,
                )

                id_ = f"{rule.class_name}({rule.property_name})"
                if id_ in ids:
                    msg = f"Relationship {rule.property_name} redefined at {row} in transformation rules!"
                    if stop_on_exception:
                        logging.error(msg)
                        raise ValueError(msg)
                    else:
                        msg += " Skipping redefinition!"
                        warnings.warn(msg, stacklevel=2)
                        logging.warning(msg)
                else:
                    relationships[row] = relationship
                    ids.add(id_)

        if relationships:
            return RelationshipDefinitions(
                data_set_id=self.metadata.data_set_id,
                prefix=self.metadata.prefix,
                namespace=self.metadata.namespace,
                relationships=relationships,
            )

        msg = "No relationship defined in transformation rule sheet!"
        if stop_on_exception:
            logging.error(msg)
            raise ValueError(msg)
        else:
            warnings.warn(msg, stacklevel=2)
            logging.warning(msg)
            return RelationshipDefinitions(
                data_set_id=self.metadata.data_set_id,
                prefix=self.metadata.prefix,
                namespace=self.metadata.namespace,
                relationships={},
            )

    def get_entity_names(self):
        class_names = set()
        property_names = set()
        for class_, properties in self.to_dataframe().items():
            class_names.add(class_)
            property_names = property_names.union(set(properties.index))
        return class_names.union(property_names)


class AssetClassMapping(BaseModel):
    external_id: str
    name: str
    parent_external_id: Optional[str]
    description: Optional[str]
    metadata: Optional[dict] = {}

    @root_validator(pre=True)
    def create_metadata(cls, values: dict):
        fields = values.keys()

        # adding metadata key in case if it is missing
        values["metadata"] = {} if "metadata" not in values else values["metadata"]

        for field in fields:
            if field not in ["external_id", "name", "parent_external_id", "data_set_id", "metadata", "description"]:
                values["metadata"][field] = ""
        return values


class AssetTemplate(BaseModel):
    """This class is used to validate, repair and wrangle rdf asset dictionary according to the
    expected format of cognite sdk Asset dataclass."""

    external_id_prefix: Optional[str] = None  # convenience field to add prefix to external_ids
    external_id: str
    name: Optional[str]
    parent_external_id: Optional[str]
    metadata: Optional[dict] = {}
    description: Optional[str]
    data_set_id: Optional[int] = None

    @root_validator(pre=True)
    def preprocess_fields(cls, values: dict):
        fields = values.keys()

        # Adding metadata key in case if it is missing
        values["metadata"] = {} if "metadata" not in values else values["metadata"]

        for field in fields:
            # Enrich: adding any field that is not in the list of expected fields to metadata
            if field not in [
                "external_id",
                "name",
                "parent_external_id",
                "data_set_id",
                "metadata",
                "description",
                "external_id_prefix",
            ]:
                values["metadata"][field] = values[field]

            # Repair: in case if name/description is list instead of single value list elements are joined
            elif field in ["name", "description"] and isinstance(values[field], list):
                msg = f"{values['type']} instance {values['identifier']} property {field} "
                msg += f"has multiple values {values[field]}, "
                msg += f"these values will be joined in a single string: {', '.join(values[field])}"
                logging.info(msg)
                values[field] = ", ".join(values[field])[: METADATA_VALUE_MAX_LENGTH - 1]

            # Repair: in case if external_id or parent_external_id are lists, we take the first value
            elif field in ["external_id", "parent_external_id"] and isinstance(values[field], list):
                msg = f"{values['type']} instance {values['identifier']} property {field} "
                msg += f"has multiple values {values[field]}, "
                msg += f"only the first one will be used: {values[field][0]}"
                logging.info(msg)
                values[field] = values[field][0]

        # Setting asset to be by default active
        values["metadata"]["active"] = "true"

        # Handling case when the external_id is not provided by defaulting to the original identifier
        # The original identifier probably has its namespace removed
        if "external_id" not in fields and "identifier" in fields:
            values["external_id"] = values["identifier"]

        return values

    @validator("metadata")
    def to_list_if_comma(cls, value):
        for key, v in value.items():
            if isinstance(v, list):
                value[key] = ", ".join(v)[: METADATA_VALUE_MAX_LENGTH - 1]
        return value

    @validator("metadata")
    def to_str(cls, value):
        for key, v in value.items():
            value[key] = str(v)
        return value

    @validator("external_id", always=True)
    def add_prefix_to_external_id(cls, value, values):
        if values["external_id_prefix"]:
            return values["external_id_prefix"] + value
        else:
            return value

    @validator("parent_external_id")
    def add_prefix_to_parent_external_id(cls, value, values):
        if values["external_id_prefix"]:
            return values["external_id_prefix"] + value
        else:
            return value


class RelationshipDefinition(BaseModel):
    source_class: str
    target_class: str
    property_: str
    labels: Optional[List[str]] = None
    target_type: str = "Asset"
    source_type: str = "Asset"
    relationship_external_id_rule: str = None


class RelationshipDefinitions(BaseModel):
    data_set_id: int
    prefix: str
    namespace: Namespace
    relationships: dict[str, RelationshipDefinition]
