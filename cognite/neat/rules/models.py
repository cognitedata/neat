from __future__ import annotations

import math
import re
import warnings
from datetime import datetime
from pathlib import Path
from typing import ClassVar, Dict, Optional

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

from cognite.neat.constants import PREFIXES

# from . import _exceptions
from cognite.neat.rules import _exceptions
from cognite.neat.rules.to_rdf_path import (
    AllReferences,
    Entity,
    Hop,
    RawLookup,
    RuleType,
    SPARQLQuery,
    SingleProperty,
    Traversal,
    parse_rule,
)

__all__ = ["Class", "Instance", "Metadata", "Prefixes", "Property", "Resource", "TransformationRules"]

# mapping of XSD types to Python and GraphQL types
DATA_TYPE_MAPPING = {
    "boolean": {"python": bool, "GraphQL": "Boolean"},
    "float": {"python": float, "GraphQL": "Float"},
    "integer": {"python": "int", "GraphQL": "Int"},
    "nonPositiveInteger": {"python": int, "GraphQL": "Int"},
    "nonNegativeInteger": {"python": int, "GraphQL": "Int"},
    "negativeInteger": {"python": "int", "GraphQL": "Int"},
    "long": {"python": int, "GraphQL": "Int"},
    "string": {"python": str, "GraphQL": "String"},
    "anyURI": {"python": str, "GraphQL": "String"},
    "normalizedString": {"python": str, "GraphQL": "String"},
    "token": {"python": str, "GraphQL": "String"},
    # Graphql does not have a datetime type this is CDF specific
    "dateTime": {"python": datetime, "GraphQL": "Timestamp"},
}


def type_to_target_convention(type_: str, target_type_convention: str) -> type:
    """Returns the GraphQL type for a given XSD type."""
    return DATA_TYPE_MAPPING[type_][target_type_convention]


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
        populate_by_name=True, str_strip_whitespace=True, arbitrary_types_allowed=True, strict=False, extra="allow"
    )

    @classmethod
    def mandatory_fields(cls, use_alias=False) -> set[str]:
        """Returns a set of mandatory fields for the model."""
        return _get_required_fields(cls, use_alias)


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


class URL(BaseModel):
    url: HttpUrl


Description = constr(min_length=1, max_length=255)

# regex expressions for compliance of Metadata sheet parsing
prefix_compliance_regex = r"^([a-zA-Z]+)([a-zA-Z0-9]*[_-]{0,1}[a-zA-Z0-9])+$"
cdf_space_name_compliance_regex = rf"(?!^(space|cdf|dms|pg3|shared|system|node|edge)$)({prefix_compliance_regex})"
data_model_name_compliance_regex = r"^([a-zA-Z]+)([a-zA-Z0-9]*[_-]{0,1}[a-zA-Z0-9])+$"
version_compliance_regex = (
    r"^([0-9]+[_-]{1}[0-9]+[_-]{1}[0-9]+[_-]{1}[a-zA-Z0-9]+)|"
    r"([0-9]+[_-]{1}[0-9]+[_-]{1}[0-9]+)|([0-9]+[_-]{1}[0-9])|([0-9]+)$"
)

Prefix = constr(min_length=1, max_length=43)
ExternalId = constr(min_length=1, max_length=255)


class Metadata(RuleModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, arbitrary_types_allowed=True
    )
    prefix: Prefix = Field(
        alias="shortName",
        description="This is used as prefix for generation of RDF OWL/SHACL data model representation",
    )
    cdf_space_name: Prefix = Field(
        description="This is used as CDF space name to which model is intend to be stored. "
        "By default it is set to 'playground'",
        alias="cdfSpaceName",
        default="playground",
    )

    namespace: Optional[Namespace] = Field(
        description="This is used as RDF namespace for generation of RDF OWL/SHACL data model representation "
        "and/or for generation of RDF graphs",
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
    source: Optional[str | Path] = Field(
        description="File path to Excel file which was used to produce Transformation Rules",
        default=None,
    )
    dms_compliant: bool = True

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

    @field_validator("version", mode="before")
    def convert_to_string(cls, value):
        return str(value)

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
        warnings.warn(_exceptions.Warning100(value).message, category=_exceptions.Warning100, stacklevel=2)
        return f"{value}#"

    @validator("data_model_name", always=True)
    def set_data_model_name_if_none(cls, value, values):
        if value is not None:
            return value
        warnings.warn(
            _exceptions.Warning101(values["prefix"].replace("-", "_")).message,
            category=_exceptions.Warning101,
            stacklevel=2,
        )
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
            warnings.warn(_exceptions.Warning102().message, category=_exceptions.Warning102, stacklevel=2)
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

    @model_validator(mode="before")
    def replace_float_nan_with_default(cls, values: dict) -> dict:
        return replace_nan_floats_with_default(values, cls.model_fields)


class_id_compliance_regex = r"^([a-zA-Z]+)([a-zA-Z0-9]+[._-]{0,1}[a-zA-Z0-9._-]+)+$"


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
            warnings.warn(
                _exceptions.Warning200(values["class_id"]).message, category=_exceptions.Warning200, stacklevel=2
            )
            value = values["class_id"]
        return value


property_id_compliance_regex = r"^(\*)|(([a-zA-Z]+)([a-zA-Z0-9]+[._-]{0,1}[a-zA-Z0-9._-]+)+)$"


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
    rule_type: Optional[RuleType] = Field(alias="Rule Type", default=None)
    rule: Optional[str | AllReferences | SingleProperty | Hop | RawLookup | SPARQLQuery | Traversal] = Field(
        alias="Rule", default=None
    )
    skip_rule: bool = Field(alias="Skip", default=False)
    mandatory: bool = False

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
            if not value:
                raise _exceptions.Error305(
                    values["property_id"], values["class_id"], values["rule_type"]
                ).to_pydantic_custom_error()
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

    # Setters
    # TODO: configure setters to only run if field_validators are successful, otherwise do not run them!
    @model_validator(mode="after")
    def set_mandatory(self):
        self.mandatory = bool(self.min_count != 0)
        return self

    @model_validator(mode="after")
    def set_property_type(self):
        if self.expected_value_type in DATA_TYPE_MAPPING.keys():
            self.property_type = "DatatypeProperty"
        else:
            self.property_type = "ObjectProperty"
        return self

    @model_validator(mode="after")
    def set_property_name_if_none(self):
        if self.property_name is None:
            warnings.warn(
                _exceptions.Warning300(self.property_id).message, category=_exceptions.Warning300, stacklevel=2
            )
            self.property_name = self.property_id
        return self

    @model_validator(mode="after")
    def set_relationship_label(self):
        if self.label is None:
            warnings.warn(
                _exceptions.Warning301(self.property_id).message, category=_exceptions.Warning301, stacklevel=2
            )
            self.label = self.property_id
        return self

    @model_validator(mode="after")
    def set_skip_rule(self):
        if self.rule_type is None:
            warnings.warn(
                _exceptions.Warning302(class_id=self.class_id, property_id=self.property_id).message,
                category=_exceptions.Warning302,
                stacklevel=2,
            )
            self.skip_rule = True
        else:
            self.skip_rule = False
        return self


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
