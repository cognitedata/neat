import re
import sys
from functools import cached_property
from typing import Literal

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum


class EntityTypes(StrEnum):
    view_non_versioned = "view_non_versioned"
    subject = "subject"
    predicate = "predicate"
    object = "object"
    class_ = "class"
    parent_class = "parent_class"
    property_ = "property"
    dms_property = "dms_property"
    information_property = "information_property"
    object_property = "ObjectProperty"
    data_property = "DatatypeProperty"
    annotation_property = "AnnotationProperty"
    object_value_type = "object_value_type"
    data_value_type = "data_value_type"  # these are strings, floats, ...
    xsd_value_type = "xsd_value_type"
    dms_value_type = "dms_value_type"
    dms_node = "dms_node"
    view = "view"
    reference_entity = "reference_entity"
    container = "container"
    datamodel = "datamodel"
    undefined = "undefined"
    multi_value_type = "multi_value_type"
    asset = "asset"
    relationship = "relationship"
    edge = "edge"
    reverse = "reverse"
    unit = "unit"
    version = "version"
    prefix = "prefix"
    space = "space"


def get_reserved_words(key: Literal["class", "view", "property", "space"]) -> list[str]:
    return {
        "class": ["Class", "class"],
        "view": [
            "Query",
            "Mutation",
            "Subscription",
            "String",
            "Int32",
            "Int64",
            "Int",
            "Float32",
            "Float64",
            "Float",
            "Timestamp",
            "JSONObject",
            "Date",
            "Numeric",
            "Boolean",
            "PageInfo",
            "File",
            "Sequence",
            "TimeSeries",
        ],
        "property": [
            "property",
            "space",
            "externalId",
            "createdTime",
            "lastUpdatedTime",
            "deletedTime",
            "edge_id",
            "node_id",
            "project_id",
            "property_group",
            "seq",
            "tg_table_name",
            "extensions",
        ],
        "space": ["space", "cdf", "dms", "pg3", "shared", "system", "node", "edge"],
    }[key]


ENTITY_PATTERN = re.compile(r"^(?P<prefix>.*?):?(?P<suffix>[^(:]*)(\((?P<content>.+)\))?$")


# REGEX FOR VALIDATIONS
MORE_THAN_ONE_NONE_ALPHANUMERIC_REGEX = r"([_-]{2,})"
PREFIX_COMPLIANCE_REGEX = r"^([a-zA-Z]+)([a-zA-Z0-9]*[_-]{0,1}[a-zA-Z0-9_-]*)([a-zA-Z0-9]*)$"

SPACE_COMPLIANCE_REGEX = (
    rf"(?!^({'|'.join(get_reserved_words('space'))})$)" r"(^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$)"
)


DATA_MODEL_COMPLIANCE_REGEX = r"^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$"

VIEW_ID_COMPLIANCE_REGEX = (
    rf"(?!^({'|'.join(get_reserved_words('view'))})$)" r"(^[a-zA-Z][a-zA-Z0-9_]{0,253}[a-zA-Z0-9]?$)"
)
DMS_PROPERTY_ID_COMPLIANCE_REGEX = (
    rf"(?!^({'|'.join(get_reserved_words('property'))})$)" r"(^[a-zA-Z][a-zA-Z0-9_]{0,253}[a-zA-Z0-9]?$)"
)
CLASS_ID_COMPLIANCE_REGEX = rf"(?!^({'|'.join(get_reserved_words('class'))})$)" r"(^[a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]?$)"

INFORMATION_PROPERTY_ID_COMPLIANCE_REGEX = r"^(\*)|(?!^(Property|property)$)(^[a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]?$)"
VERSION_COMPLIANCE_REGEX = r"^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$"


# This pattern ignores commas inside brackets
SPLIT_ON_COMMA_PATTERN = re.compile(r",(?![^(]*\))")
# This pattern ignores equal signs inside brackets
SPLIT_ON_EQUAL_PATTERN = re.compile(r"=(?![^(]*\))")

# Very special Edge Entity parsing
SPLIT_ON_EDGE_ENTITY_ARGS_PATTERN = re.compile(r"(\btype\b|\bproperties\b|\bdirection\b)\s*=\s*([^,]+)")


class _Patterns:
    @cached_property
    def more_than_one_alphanumeric(self) -> re.Pattern:
        return re.compile(MORE_THAN_ONE_NONE_ALPHANUMERIC_REGEX)

    @cached_property
    def prefix_compliance(self) -> re.Pattern[str]:
        return re.compile(PREFIX_COMPLIANCE_REGEX)

    @cached_property
    def space_compliance(self) -> re.Pattern[str]:
        return re.compile(SPACE_COMPLIANCE_REGEX)

    @cached_property
    def view_id_compliance(self) -> re.Pattern[str]:
        return re.compile(VIEW_ID_COMPLIANCE_REGEX)

    @cached_property
    def dms_property_id_compliance(self) -> re.Pattern[str]:
        return re.compile(DMS_PROPERTY_ID_COMPLIANCE_REGEX)

    @cached_property
    def class_id_compliance(self) -> re.Pattern[str]:
        return re.compile(CLASS_ID_COMPLIANCE_REGEX)

    @cached_property
    def information_property_id_compliance(self) -> re.Pattern[str]:
        return re.compile(INFORMATION_PROPERTY_ID_COMPLIANCE_REGEX)

    @cached_property
    def version_compliance(self) -> re.Pattern[str]:
        return re.compile(VERSION_COMPLIANCE_REGEX)

    def entity_pattern(
        self,
        entity: EntityTypes,
    ) -> re.Pattern:
        if entity == EntityTypes.class_:
            return self.class_id_compliance

        elif entity == EntityTypes.information_property:
            return self.information_property_id_compliance

        elif entity == EntityTypes.view:
            return self.view_id_compliance

        # container regex same as view regex
        elif entity == EntityTypes.container:
            return self.view_id_compliance

        elif entity == EntityTypes.dms_property:
            return self.dms_property_id_compliance

        elif entity == EntityTypes.version:
            return self.version_compliance

        elif entity == EntityTypes.prefix:
            return self.prefix_compliance

        elif entity == EntityTypes.space:
            return self.space_compliance

        else:
            raise ValueError(f"Unsupported entity type {entity}")


PATTERNS = _Patterns()


def get_internal_properties() -> set[str]:
    return {
        "physical",
        "logical",
        "conceptual",
        "Neat ID",
    }
