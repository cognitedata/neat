"""This module performs importing of various formats to one of serializations for which
there are loaders to data model pydantic class."""

from cognite.neat.core._data_model.importers._rdf._base import BaseRDFImporter
from cognite.neat.core._data_model.importers._rdf._shared import (
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

PROPERTIES_QUERY = """

    SELECT ?concept  ?property_ ?name ?description ?value_type ?minCount ?maxCount ?default
    WHERE {{
        ?property_ a ?property_Type.
        FILTER (?property_Type IN (owl:ObjectProperty, owl:DatatypeProperty ) )
        OPTIONAL {{?property_ rdfs:domain ?concept  }}.
        OPTIONAL {{?property_ rdfs:range ?value_type }}.
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


class OWLImporter(BaseRDFImporter):
    """Convert OWL ontology to unverified data model.

        Args:
            filepath: Path to OWL ontology

    !!! Note
        OWL Ontologies are information models which completeness varies. As such, constructing functional
        data model directly will often be impossible, therefore the produced data model object will be ill formed.
        To avoid this, neat will automatically attempt to make the imported data model compliant by adding default
        values for missing information, attaching dangling properties to default containers based on the
        property type, etc.

        One has to be aware that NEAT will be opinionated about how to make the ontology
        compliant, and that the resulting data model may not be what you expect.

    """

    def _to_data_model_components(
        self,
    ) -> dict:
        concepts, issue_list = parse_concepts(self.graph, CLASSES_QUERY, self.language, self.issue_list)
        self.issue_list = issue_list

        # NeatError
        properties, issue_list = parse_properties(self.graph, PROPERTIES_QUERY, self.language, self.issue_list)
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
