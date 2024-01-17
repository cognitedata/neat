import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from cognite.neat.rules import exceptions
from cognite.neat.rules.analysis import to_class_property_pairs
from cognite.neat.rules.exporter._validation import are_entity_names_dms_compliant, are_properties_redefined
from cognite.neat.rules.models.rules import Rules
from cognite.neat.rules.models.value_types import XSD_VALUE_TYPE_MAPPINGS
from cognite.neat.utils.utils import generate_exception_report

from ._base import BaseExporter

if TYPE_CHECKING:
    from jinja2 import Template


class GraphQLSchemaExporter(BaseExporter[str]):
    def _export_to_file(self, filepath: Path):
        if filepath.suffix != ".graphql":
            warnings.warn("File extension is not .graphql, adding it to the file name", stacklevel=2)
            filepath = filepath.with_suffix(".graphql")
        filepath.write_text(self.export())

    def export(self) -> str:
        return GraphQLSchema.from_rules(self.rules).schema


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

_FIELD_VALUE_TYPE = """{{property_definition.expected_value_type.mapping.graphql
                if property_definition.expected_value_type.suffix in value_type_mapping
                else property_definition.expected_value_type.suffix}}"""


@dataclass
class GraphQLSchema:
    """
    Represents a GraphQL schema.

    This can be used to generate a GraphQL schema from TransformationRules.

    Args:
        schema: The GraphQL schema.

    """

    schema: str

    @classmethod
    def from_rules(cls, transformation_rules: Rules, verbose: bool = False) -> Self:
        """
        Generates a GraphQL schema from TransformationRules.

        Args:
            transformation_rules: The TransformationRules to generate a GraphQL schema from.
            verbose: Whether to include descriptions and names in the schema.

        Returns:
            A GraphQLSchema instance.
        """
        names_compliant, name_warnings = are_entity_names_dms_compliant(transformation_rules, return_report=True)
        if not names_compliant:
            raise exceptions.EntitiesContainNonDMSCompliantCharacters(report=generate_exception_report(name_warnings))

        properties_redefined, redefinition_warnings = are_properties_redefined(transformation_rules, return_report=True)
        if properties_redefined:
            raise exceptions.PropertiesDefinedMultipleTimes(report=generate_exception_report(redefinition_warnings))

        return cls(schema=cls.generate_schema(transformation_rules, verbose))

    @staticmethod
    def generate_schema(transformation_rules: Rules, verbose: bool) -> str:
        """
        Generates a GraphQL schema from TransformationRules.

        Args:
            transformation_rules: Instance of TransformationRules to generate a GraphQL schema from.
            verbose: Whether to include descriptions and names in the schema.

        Returns:
            A GraphQL schema.
        """
        class_properties = to_class_property_pairs(transformation_rules)

        type_definitions = []

        for class_id in class_properties:
            parameters = {
                "class_definition": transformation_rules.classes[class_id],
                "class_properties": list(class_properties[class_id].values()),
                "value_type_mapping": XSD_VALUE_TYPE_MAPPINGS,
                "header": verbose,
            }

            type_definitions.append(GraphQLSchema.template().render(parameters))

        return "\n\n".join(type_definitions)

    @staticmethod
    def template() -> "Template":
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
