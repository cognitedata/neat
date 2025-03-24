"""This module performs importing of various formats to one of serializations for which
there are loaders to TransformationRules pydantic class."""

import copy
import re
from typing import Self
from uuid import UUID

from cognite.neat._rules.importers._rdf._base import BaseRDFImporter
from cognite.neat._rules.importers._rdf._shared import parse_classes, parse_properties

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
        mapped_classes = self._map_to_base_model(classes)
        compliant_classes = self._make_compliant(mapped_classes, ["class_"])

        self.issue_list = issue_list

        properties, issue_list = parse_properties(self.graph, PROPERTIES_QUERY, self.language, self.issue_list)
        compliant_properties = self._make_compliant(properties, ["class_", "property_"])
        self.issue_list = issue_list

        components = {
            "Metadata": self._metadata,
            "Classes": compliant_classes if classes else [],
            "Properties": compliant_properties if properties else [],
        }

        return components

    @classmethod
    def from_file(cls, *args, **kwargs) -> Self:
        if "data_model_id" not in kwargs:
            kwargs["data_model_id"] = DEFAULT_IMF_DATA_MODEL_ID
        return super().from_file(*args, **kwargs)

    @classmethod
    def _map_to_base_model(cls, classes: dict[str, dict]) -> dict[str, dict]:
        mapped_classes = copy.deepcopy(classes)
        for key, value in classes.items():
            if value["implements"] == "Block":
                mapped_classes[key]["implements"] = "imf_base:Block(version=v1)"
            elif value["implements"] == "Terminal":
                mapped_classes[key]["implements"] = "imf_base:Terminal(version=v1)"

        return mapped_classes

    @classmethod
    def _make_compliant(cls, entities: dict[str, dict], fields_to_update: list) -> list:
        updated_entities: list = []

        for _, value in entities.items():
            updated_entity = {**value}

            for field in fields_to_update:
                updated_entity[field] = cls._fix_entity(value[field], "IMF")

            updated_entities.append(updated_entity)

        return updated_entities

    @classmethod
    def _fix_entity(cls, entity: str, prefix: str = "prefix") -> str:
        if cls._is_valid_uuid(entity):
            entity = prefix + "_" + entity

        entity = re.sub(r"[^_a-zA-Z0-9]+", "_", entity)

        # removing any double underscores that could occur
        return re.sub(r"[^a-zA-Z0-9]+", "_", entity)

    @classmethod
    def _is_valid_uuid(cls, uuid_to_test: str, version: int = 4) -> bool:
        try:
            uuid_obj = UUID(uuid_to_test, version=version)
            return str(uuid_obj) == uuid_to_test
        except ValueError:
            return False
