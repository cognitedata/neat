"""This module performs importing of various formats to one of serializations for which
there are loaders to data model pydantic class."""

from cognite.neat._v0.core._data_model.importers._rdf._base import BaseRDFImporter
from cognite.neat._v0.core._data_model.importers._rdf._shared import (
    parse_concepts,
    parse_properties,
)

CLASSES_QUERY = """SELECT ?concept  ?name ?description ?implements
        WHERE {{

        ?concept  a owl:Class .
        OPTIONAL {{?concept  rdfs:subClassOf ?implements }}.
        OPTIONAL {{?concept  rdfs:label|skos:prefLabel ?name }}.
        OPTIONAL {{?concept  rdfs:comment|skos:definition ?description}} .


        FILTER (!isBlank(?concept ))
        FILTER (!bound(?implements) || !isBlank(?implements))

        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "{language}"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "{language}"))

    }}
    """

CLASSES_QUERY_PARAMETERS = {"concept", "name", "description", "implements"}

PROPERTIES_QUERY = """ SELECT ?concept ?property_ ?name ?description ?value_type ?min_count ?max_count ?default
    WHERE {{
        ?property_ a ?property_Type.
        FILTER (?property_Type IN (owl:ObjectProperty, owl:DatatypeProperty ) )

        # --- 1. Explicit Domain Discovery ---

        # A. Handling owl:domain when it is expressed as owl restriction
        OPTIONAL {{
            ?property_ rdfs:domain ?domain_exp_node .
            FILTER(isBlank(?domain_exp_node))
            ?domain_exp_node owl:unionOf|owl:intersectionOf ?exp_concepts_list .
            ?exp_concepts_list rdf:rest*/rdf:first ?explicit_concept.
        }}

        # B. Handling the domain when it is a single concept
        OPTIONAL {{
            ?property_ rdfs:domain ?domain_exp_node .
            FILTER(!isBlank(?domain_exp_node))
            BIND(?domain_exp_node AS ?explicit_concept)
        }}

        # --- 2. Inherited Domain Discovery (Fallback) ---

        # C. Handling inherited domain when parent domain is a restriction
        OPTIONAL {{
            ?property_ rdfs:subPropertyOf ?parent_property .
            ?parent_property rdfs:domain ?parent_domain_node .
            FILTER(isBlank(?parent_domain_node))
            ?parent_domain_node owl:unionOf|owl:intersectionOf ?parent_concepts_list .
            ?parent_concepts_list rdf:rest*/rdf:first ?inherited_concept.
        }}

        # D. Handling inherited domain when parent domain is a single concept
        OPTIONAL {{
            ?property_ rdfs:subPropertyOf ?parent_property .
            ?parent_property rdfs:domain ?parent_domain_node .
            FILTER(!isBlank(?parent_domain_node))
            BIND(?parent_domain_node AS ?inherited_concept)
        }}

        # Final Concept Assignment with Priority ---
        # COALESCE prioritizes ?explicit_concept over ?inherited_concept
        BIND(COALESCE(?explicit_concept, ?inherited_concept) AS ?concept)


        # Handling owl:range when it is expressed as owl restriction
        OPTIONAL {{
            ?property_ rdfs:range ?range .
            FILTER(isBlank(?range))
            ?range owl:unionOf|owl:intersectionOf ?value_types .
            ?value_types rdf:rest*/rdf:first ?value_type.
        }}

        # Handling the range when it is a single concept
        OPTIONAL {{
            ?property_ rdfs:range ?range .
            FILTER(!isBlank(?range))
            BIND(?range AS ?value_type)
        }}

        OPTIONAL {{?property_ rdfs:label|skos:prefLabel ?name }}.
        OPTIONAL {{?property_ rdfs:comment|skos:definition ?description}}.
        OPTIONAL {{?property_ owl:maxCardinality ?max_count}}.
        OPTIONAL {{?property_ owl:minCardinality ?min_count}}.

        # FILTERS
        FILTER (!isBlank(?property_))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "{language}"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "{language}"))
    }}
    """
PROPERTIES_QUERY_PARAMETERS = {
    "concept",
    "property_",
    "name",
    "description",
    "value_type",
    "min_count",
    "max_count",
    "default",
}


class OWLImporter(BaseRDFImporter):
    """Convert OWL ontology to unverified data model.

    Args:
        filepath: Path to OWL ontology
    """

    def _to_data_model_components(
        self,
    ) -> dict:
        concepts, issue_list = parse_concepts(
            self.graph, CLASSES_QUERY, CLASSES_QUERY_PARAMETERS, self.language, self.issue_list
        )
        self.issue_list = issue_list

        properties, issue_list = parse_properties(
            self.graph, PROPERTIES_QUERY, PROPERTIES_QUERY_PARAMETERS, self.language, self.issue_list
        )
        self.issue_list = issue_list

        components = {
            "Metadata": self._metadata,
            "Concepts": list(concepts.values()) if concepts else [],
            "Properties": list(properties.values()) if properties else [],
        }

        return components

    @property
    def description(self) -> str:
        return f"Ontology {self.source_name} read as unverified data model"
