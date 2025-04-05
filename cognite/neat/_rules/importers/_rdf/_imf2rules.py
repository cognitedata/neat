"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

from pathlib import Path
from typing import Self

from cognite.client import data_modeling as dm

from cognite.neat._rules.importers._rdf._base import BaseRDFImporter
from cognite.neat._rules.importers._rdf._shared import parse_classes, parse_properties
from cognite.neat._rules.models.data_types import AnyURI
from cognite.neat._rules.models.entities import UnknownEntity

DEFAULT_NON_EXISTING_NODE_TYPE = AnyURI()

IMF_DATA_MODEL_ID = ("imf_instances", "RDFDataModel", "1")

CLASSES_QUERY = """
    SELECT ?class_ ?name ?description ?implements ?instance_source
    WHERE {{
        VALUES ?implements {{ imf:Block imf:Terminal }}
        ?class_ rdfs:subClassOf ?implements .

        OPTIONAL {{?class_ rdfs:label|skos:prefLabel ?name }}.
        OPTIONAL {{?class_ rdfs:comment|skos:definition ?description}}.

        BIND(?class_ AS ?instance_source)

        # FILTERS
        FILTER (!isBlank(?class_))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "{language}"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "{language}"))
    }}
    """

PROPERTIES_QUERY = """
    SELECT ?class_ ?property_ ?name ?description ?value_type ?instance_source ?min_count ?max_count ?default
    WHERE
    {{
        VALUES ?subClass {{ imf:Block imf:Terminal }}
        ?class_ rdfs:subClassOf ?subClass ;
            sh:property ?propertyShape .
            ?propertyShape sh:path ?property_ .

        OPTIONAL {{ ?property_ skos:prefLabel ?name . }}
        OPTIONAL {{ ?property_ skos:definition ?description . }}
        OPTIONAL {{ ?property_ rdfs:range ?range . }}

        OPTIONAL {{ ?propertyShape sh:minCount ?min_count . }}
        OPTIONAL {{ ?propertyShape sh:maxCount ?max_count . }}
        OPTIONAL {{ ?propertyShape sh:nodeKind ?nodeKind . }}
        OPTIONAL {{ ?propertyShape sh:hasValue ?default . }}

        BIND(?property_ AS ?instance_source)
        BIND(IF(BOUND(?range), ?range, xsd:string) AS ?value_type)
        BIND(IF(BOUND(?default) && !BOUND(?min_count), 1, 0) AS ?min_count)
        BIND(IF(BOUND(?default) && !BOUND(?max_count), 1, ?undefined) AS ?max_count)

        FILTER(?property_ != imf:hasTerminal && ?property_ != imf:hasPart)

        FILTER (!isBlank(?property_))
        FILTER (!bound(?class_) || !isBlank(?class_))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "{language}"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "{language}"))
    }}
    """
DEFAULT_IMF_DATA_MODEL_ID = ("imf_instances", "imf_types_instance_data", "v1")


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

    @classmethod
    def from_file(
        cls,
        filepath: Path,
        data_model_id: dm.DataModelId | tuple[str, str, str] = DEFAULT_IMF_DATA_MODEL_ID,
        max_number_of_instance: int = -1,
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
        language: str = "en",
        source_name: str = "Unknown",
    ) -> Self:
        return super().from_file(
            filepath, data_model_id, max_number_of_instance, non_existing_node_type, language, source_name
        )
