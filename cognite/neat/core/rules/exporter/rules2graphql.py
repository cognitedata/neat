from cognite.neat.core.rules import _exceptions
from jinja2 import DictLoader, Environment
from cognite.neat.core.rules._validation import (
    are_entity_names_dms_compliant,
    are_properties_redefined,
)

from cognite.neat.core.rules.analysis import get_class_property_pairs
from cognite.neat.core.rules.models import DATA_TYPE_MAPPING, TransformationRules
from cognite.neat.core.utils.utils import generate_exception_report


TYPE = (
    "{% include 'type_header' %}type {{ class_definition.class_id }} {{'{'}}"
    "{%-for property_definition in class_properties%}"
    "{% include 'field' %}"
    "{% endfor %}\n}\n"
)

TYPE_HEADER = (
    "{%- if header %}"
    "{%- if class_definition.description and class_definition.class_name %}"
    '"""\n{{class_definition.description}}\n@name {{ class_definition.class_name }}\n"""\n{##}\n'
    "{%- elif class_definition.description %}"
    '\n"""\n{{class_definition.description}}\n"""\n'
    "{%- endif %}"
    "{%- endif %}"
)


FIELD = (
    "{% include 'field_header' %}\n"
    "  {{ property_definition.property_id }}: "
    "{%-if property_definition.property_type == 'DatatypeProperty'%}"
    "{% include 'attribute_occurrence' %}"
    "{%-else%}"
    "{% include 'edge_occurrence' %}"
    "{%- endif -%}"
)

FIELD_HEADER = (
    "{%- if header %}"
    "{%- if property_definition.description and property_definition.property_name %}"
    '\n  """\n  {{property_definition.description}}'
    "\n  @name {{ property_definition.property_name }}"
    '\n  """\n  '
    "{%- elif property_definition.description %}"
    '\n  """\n  {{property_definition.description}}'
    '\n  """\n  '
    "{%- endif %}"
    "{%- endif %}"
)

ATTRIBUTE_OCCURRENCE = (
    "{%-if property_definition.min_count and property_definition.max_count == 1%}"
    " {% include 'value_type' %}!"
    "{%-elif property_definition.min_count and property_definition.max_count != 1%}"
    " [{% include 'value_type' %}!]!"
    "{%-elif property_definition.max_count != 1%}"
    " [{% include 'value_type' %}!]!"
    "{%-else%}{% include 'value_type' %}"
    "{%- endif -%}"
)

EDGE_OCCURRENCE = (
    "{%-if not(property_definition.min_count and property_definition.max_count == 1)%}"
    " [{% include 'value_type' %}]"
    "{%-else%}"
    " {% include 'value_type' %}"
    "{%- endif -%}"
)

FIELD_VALUE_TYPE = """{{value_type_mapping[property_definition.expected_value_type]['GraphQL']
                if property_definition.expected_value_type in value_type_mapping
                else property_definition.expected_value_type}}"""


rules2graphql_template = Environment(
    loader=DictLoader(
        {
            "type_header": TYPE_HEADER,
            "type": TYPE,
            "field_header": FIELD_HEADER,
            "field": FIELD,
            "value_type": FIELD_VALUE_TYPE,
            "edge_occurrence": EDGE_OCCURRENCE,
            "attribute_occurrence": ATTRIBUTE_OCCURRENCE,
        }
    ),
    cache_size=1000,
).get_template("type")


def rules2graphql_schema(
    transformation_rules: TransformationRules,
    header: bool = False,
) -> str:
    """Generates a GraphQL schema from an instance of TransformationRules

    Parameters
    ----------
    transformation_rules : TransformationRules
        TransformationRules object

    Returns
    -------
    str
        GraphQL schema string
    """
    names_compliant, name_warnings = are_entity_names_dms_compliant(transformation_rules, return_report=True)
    properties_redefined, redefinition_warnings = are_properties_redefined(transformation_rules, return_report=True)

    if not names_compliant:
        raise _exceptions.Error10(report=generate_exception_report(name_warnings))
    if properties_redefined:
        raise _exceptions.Error11(report=generate_exception_report(redefinition_warnings))

    class_properties = get_class_property_pairs(transformation_rules)

    type_definitions = []

    for class_id in class_properties:
        parameters = {
            "class_definition": transformation_rules.classes[class_id],
            "class_properties": list(class_properties[class_id].values()),
            "value_type_mapping": DATA_TYPE_MAPPING,
            "header": header,
        }

        type_definitions.append(rules2graphql_template.render(parameters))

    return "\n\n".join(type_definitions)
