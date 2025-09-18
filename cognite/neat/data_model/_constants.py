import re
import sys

from ._identifiers import NameSpace

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum


XML_SCHEMA_NAMESPACE = NameSpace("http://www.w3.org/2001/XMLSchema#")

# This pattern ignores commas inside brackets
SPLIT_ON_COMMA_PATTERN = re.compile(r",(?![^(]*\))")
# This pattern ignores equal signs inside brackets
SPLIT_ON_EQUAL_PATTERN = re.compile(r"=(?![^(]*\))")


class EntityTypes(StrEnum):
    view_non_versioned = "view_non_versioned"
    subject = "subject"
    predicate = "predicate"
    object = "object"
    class_ = "class"
    concept = "concept"
    parent_class = "parent_class"
    property_ = "property"
    physical_property = "physical_property"
    conceptual_property = "conceptual_property"
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
    container_index = "container_index"
    concept_restriction = "conceptRestriction"
    value_constraint = "valueConstraint"
    cardinality_constraint = "cardinalityConstraint"
    named_individual = "named_individual"
