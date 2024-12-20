"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

from cognite.neat._rules.importers._rdf._base import BaseRDFImporter
from cognite.neat._rules.importers._rdf._shared import parse_classes, parse_properties

CLASSES_QUERY = """
    SELECT ?class_ ?name ?description ?implements
    WHERE {{
        VALUES ?type {{ imf:BlockType imf:TerminalType imf:AttributeType }}
        ?class_ a ?type .

        OPTIONAL {{?class_ rdfs:subClassOf ?parent }}.
        OPTIONAL {{?class_ rdfs:label|skos:prefLabel ?name }}.
        OPTIONAL {{?class_ rdfs:comment|skos:definition ?description}}.


        # Add imf:Attribute as parent class when no parent is found
        BIND(IF(!bound(?parent) && ?type = imf:AttributeType, imf:Attribute, ?parent) AS ?implements)

        # FILTERS
        FILTER (!isBlank(?class_))
        FILTER (!bound(?implements) || !isBlank(?implements))

        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "{language}"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "{language}"))
    }}
    """

PROPERTIES_QUERY = """
    SELECT ?class_ ?property_ ?name ?description ?value_type ?min_count ?max_count ?default
    WHERE
    {{
        # CASE 1: Handling Blocks and Terminals
        {{
            VALUES ?type {{ imf:BlockType imf:TerminalType }}
            ?class_ a ?type ;
                sh:property ?propertyShape .
                ?propertyShape sh:path ?property_ .

            OPTIONAL {{ ?property_ skos:prefLabel ?name . }}
            OPTIONAL {{ ?property_ skos:definition ?description . }}
            OPTIONAL {{ ?property_ rdfs:range ?range . }}

            OPTIONAL {{ ?propertyShape sh:minCount ?min_count . }}
            OPTIONAL {{ ?propertyShape sh:maxCount ?max_count . }}
            OPTIONAL {{ ?propertyShape sh:hasValue ?default . }}
            OPTIONAL {{ ?propertyShape sh:class | sh:qualifiedValueShape/sh:class ?valueShape . }}
        }}

        UNION

        # CASE 2: Handling Attributes
        {{
            ?class_ a imf:AttributeType .
            BIND(xsd:anyURI AS ?valueShape)
            BIND(imf:predicate AS ?property_)
            ?class_  ?property_ ?defaultURI .
            BIND(STR(?defaultURI) AS ?default)

        }}

        # Set the value type for the property based on sh:class, sh:qualifiedValueType or rdfs:range
        BIND(IF(BOUND(?valueShape), ?valueShape, IF(BOUND(?range) , ?range , ?valueShape)) AS ?value_type)

        FILTER (!isBlank(?property_))
        FILTER (!bound(?class_) || !isBlank(?class_))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "{language}"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "{language}"))
    }}
    """


class IMFImporter(BaseRDFImporter):
    """Convert IMF Types provided as SHACL shapes to Input Rules."""

    @property
    def description(self) -> str:
        return f"IMF Types {self.source_name} read as unverified data model"

    def _to_rules_components(
        self,
    ) -> dict:
        classes, issue_list = parse_classes(self.graph, CLASSES_QUERY, self.language, self.issue_list)
        self.issue_list = issue_list
        properties, issue_list = parse_properties(self.graph, PROPERTIES_QUERY, self.language, self.issue_list)
        self.issue_list = issue_list

        components = {
            "Metadata": self._metadata,
            "Classes": list(classes.values()) if classes else [],
            "Properties": list(properties.values()) if properties else [],
        }

        return components
