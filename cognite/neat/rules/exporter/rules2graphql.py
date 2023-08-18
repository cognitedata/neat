from dataclasses import dataclass
from typing import Self
from cognite.neat.rules import exceptions
from cognite.neat.rules._validation import (
    are_entity_names_dms_compliant,
    are_properties_redefined,
)
from cognite.neat.rules.analysis import to_class_property_pairs
from cognite.neat.rules.models import DATA_TYPE_MAPPING, TransformationRules
from cognite.neat.utils.utils import generate_exception_report


_TYPE = (
    "{% include 'type_header' %}type {{ class_definition.class_id }} {{'{'}}"
    "{%-for property_definition in class_properties%}"
    "{% include 'field' %}"
    "{% endfor %}\n}\n"
)

_TYPE_HEADER = (
    "{%- if header %}"
    "{%- if class_definition.description and class_definition.class_name %}"
    '"""\n{{class_definition.description}}\n@name {{ class_definition.class_name }}\n"""\n{##}\n'
    "{%- elif class_definition.description %}"
    '\n"""\n{{class_definition.description}}\n"""\n'
    "{%- endif %}"
    "{%- endif %}"
)


_FIELD = (
    "{% include 'field_header' %}\n"
    "  {{ property_definition.property_id }}: "
    "{%-if property_definition.property_type == 'DatatypeProperty'%}"
    "{% include 'attribute_occurrence' %}"
    "{%-else%}"
    "{% include 'edge_occurrence' %}"
    "{%- endif -%}"
)

_FIELD_HEADER = (
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

_ATTRIBUTE_OCCURRENCE = (
    "{%-if property_definition.min_count and property_definition.max_count == 1%}"
    " {% include 'value_type' %}!"
    "{%-elif property_definition.min_count and property_definition.max_count != 1%}"
    " [{% include 'value_type' %}!]!"
    "{%-elif property_definition.max_count != 1%}"
    " [{% include 'value_type' %}!]!"
    "{%-else%}{% include 'value_type' %}"
    "{%- endif -%}"
)

_EDGE_OCCURRENCE = (
    "{%-if not(property_definition.min_count and property_definition.max_count == 1)%}"
    " [{% include 'value_type' %}]"
    "{%-else%}"
    " {% include 'value_type' %}"
    "{%- endif -%}"
)

_FIELD_VALUE_TYPE = """{{value_type_mapping[property_definition.expected_value_type]['GraphQL']
                if property_definition.expected_value_type in value_type_mapping
                else property_definition.expected_value_type}}"""


@dataclass
class GraphQLSchema:
    """Abilities to generate a GraphQL schema from TransformationRules"""

    schema: str

    @classmethod
    def from_rules(cls, transformation_rules: TransformationRules, verbose: bool = False) -> Self:
        names_compliant, name_warnings = are_entity_names_dms_compliant(transformation_rules, return_report=True)
        if not names_compliant:
            raise exceptions.EntitiesContainNonDMSCompliantCharacters(report=generate_exception_report(name_warnings))

        properties_redefined, redefinition_warnings = are_properties_redefined(transformation_rules, return_report=True)
        if properties_redefined:
            raise exceptions.PropertiesDefinedMultipleTimes(report=generate_exception_report(redefinition_warnings))

        return cls(schema=cls.generate_schema(transformation_rules, verbose))

    @staticmethod
    def generate_schema(transformation_rules: TransformationRules, verbose: bool) -> str:
        """Generates a GraphQL schema of given TransformationRules"""
        class_properties = to_class_property_pairs(transformation_rules)

        type_definitions = []

        for class_id in class_properties:
            parameters = {
                "class_definition": transformation_rules.classes[class_id],
                "class_properties": list(class_properties[class_id].values()),
                "value_type_mapping": DATA_TYPE_MAPPING,
                "header": verbose,
            }

            type_definitions.append(GraphQLSchema.template().render(parameters))

        return "\n\n".join(type_definitions)

    @staticmethod
    def template():
        from jinja2 import DictLoader, Environment, Template

        template: Template = Environment(
            loader=DictLoader(
                {
                    "type_header": _TYPE_HEADER,
                    "type": _TYPE,
                    "field_header": _FIELD_HEADER,
                    "field": _FIELD,
                    "value_type": _FIELD_VALUE_TYPE,
                    "edge_occurrence": _EDGE_OCCURRENCE,
                    "attribute_occurrence": _ATTRIBUTE_OCCURRENCE,
                }
            ),
            cache_size=1000,
        ).get_template("type")
        return template
