import re
import sys

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


# ALLOWED
_ALLOWED_PATTERN = r"[^a-zA-Z0-9-_.]"

# FOR PARSING STRINGS:
_PREFIX_REGEX = r"[a-zA-Z]+[a-zA-Z0-9-_.]*[a-zA-Z0-9]+"
_SUFFIX_REGEX = r"[a-zA-Z0-9-_.]+[a-zA-Z0-9]|[-_.]*[a-zA-Z0-9]+"
_VERSION_REGEX = r"[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?"
_PROPERTY_REGEX = r"[a-zA-Z0-9][a-zA-Z0-9_-]*[a-zA-Z0-9]?"
_ENTITY_ID_REGEX = rf"{_PREFIX_REGEX}:({_SUFFIX_REGEX})"
_ENTITY_ID_REGEX_COMPILED = re.compile(rf"^(?P<prefix>{_PREFIX_REGEX}):(?P<suffix>{_SUFFIX_REGEX})$")
_VERSIONED_ENTITY_REGEX_COMPILED = re.compile(
    rf"^(?P<prefix>{_PREFIX_REGEX}):(?P<suffix>{_SUFFIX_REGEX})\(version=(?P<version>{_VERSION_REGEX})\)$"
)
_CLASS_ID_REGEX = rf"(?P<{EntityTypes.class_}>{_ENTITY_ID_REGEX})"
_CLASS_ID_REGEX_COMPILED = re.compile(rf"^{_CLASS_ID_REGEX}$")
_PROPERTY_ID_REGEX = rf"\((?P<{EntityTypes.property_}>{_ENTITY_ID_REGEX})\)"

ENTITY_PATTERN = re.compile(r"^(?P<prefix>.*?):?(?P<suffix>[^(:]*)(\((?P<content>.+)\))?$")
MULTI_VALUE_TYPE_PATTERN = re.compile(r"^(?P<types>.*?)(\((?P<content>[^)]+)\))?$")
# This pattern ignores commas inside brackets
SPLIT_ON_COMMA_PATTERN = re.compile(r",(?![^(]*\))")
# This pattern ignores equal signs inside brackets
SPLIT_ON_EQUAL_PATTERN = re.compile(r"=(?![^(]*\))")
