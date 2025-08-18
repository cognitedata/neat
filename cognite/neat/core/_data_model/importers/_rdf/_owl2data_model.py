"""This module performs importing of various formats to one of serializations for which
there are loaders to data model pydantic class."""

from cognite.neat.core._data_model.importers._rdf._base import BaseRDFImporter
from cognite.neat.core._data_model.importers._rdf._shared import (
    parse_concepts,
    parse_properties,
    parse_restriction,
)

CLASSES_QUERY = """SELECT ?concept  ?name ?description ?implements
        WHERE {{

        ?concept  a owl:Class .
        OPTIONAL {{?concept  rdfs:subClassOf ?subclasses }}.
        OPTIONAL {{?concept  rdfs:label|skos:prefLabel ?name }}.
        OPTIONAL {{?concept  rdfs:comment|skos:definition ?description}} .


        FILTER (!isBlank(?concept))

        # usage of restrictions are handling this usecase
        BIND(IF(isBlank(?subclasses), "", ?subclasses) AS ?implements)        

        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "{language}"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "{language}"))

    }}
    """

CLASSES_QUERY_PARAMETERS = {"concept", "name", "description", "implements"}

PROPERTIES_QUERY = """

    SELECT ?concept  ?property_ ?name ?description ?value_type ?minCount ?maxCount ?default
    WHERE {{
        ?property_ a ?property_Type.
        FILTER (?property_Type IN (owl:ObjectProperty, owl:DatatypeProperty ) )



        # Handling owl:domain when it is expressed as
        # owl restriction
        OPTIONAL {{
            ?property_ rdfs:domain ?domain .
            FILTER(isBlank(?domain))
            ?domain owl:unionOf|owl:intersectionOf ?concepts .
            ?concepts rdf:rest*/rdf:first ?concept.
        }}

        # Handling the domain when it is a single concept
        OPTIONAL {{
            ?property_ rdfs:domain ?domain .
            FILTER(!isBlank(?domain))
            BIND(?domain AS ?concept)
        }}

        # Handling owl:range when it is expressed as
        # owl restriction
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
        OPTIONAL {{?property_ owl:maxCardinality ?maxCount}}.
        OPTIONAL {{?property_ owl:minCardinality ?minCount}}.

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
    "minCount",
    "maxCount",
    "default",
}


RESTRICTION_QUERY = """
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>

SELECT ?concept ?property_ ?valueConstraint ?value ?cardinalityConstraint ?cardinality ?on
WHERE {
    ?concept rdf:type owl:Class .
    ?concept rdfs:subClassOf ?restriction .
    ?restriction rdf:type owl:Restriction .
    ?restriction owl:onProperty ?property_ .

    OPTIONAL {
        ?restriction owl:hasValue|owl:someValuesFrom|owl:allValuesFrom ?value .
        ?restriction ?valueConstraint ?value .
    }

    
   OPTIONAL {
        ?restriction owl:minCardinality|owl:maxCardinality|owl:cardinality|owl:qualifiedCardinality ?cardinality .
        ?restriction ?cardinalityConstraint ?cardinality .
        OPTIONAL {
            ?restriction owl:onClass|owl:onDataRange ?on .
        }
    }


    
}
"""

RESTRICTION_QUERY_PARAMETERS = {
    "concept",
    "property_",
    "valueConstraint",
    "value",
    "cardinalityConstraint",
    "cardinality",
    "on",
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

        restrictions, issue_list = parse_restriction(
            self.graph, RESTRICTION_QUERY, RESTRICTION_QUERY_PARAMETERS, self.issue_list
        )

        for concept, restrictions in restrictions.items():
            if concept in concepts:
                concepts[concept]["restrictions"] = restrictions

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
