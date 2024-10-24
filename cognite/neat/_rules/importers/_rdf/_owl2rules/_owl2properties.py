from typing import cast

from rdflib import Graph

from cognite.neat._rules.importers._rdf._shared import (
    clean_up_properties,
    make_properties_compliant,
    parse_raw_properties_dataframe,
)


def parse_owl_properties(graph: Graph, language: str = "en") -> list[dict]:
    """Parse owl properties from graph to pandas dataframe.

    Args:
        graph: Graph containing owl properties
        language: Language to use for parsing, by default "en"

    Returns:
        List of dictionaries containing owl properties
    """

    query = """

    SELECT ?class ?property ?name ?description ?type ?minCount ?maxCount ?default ?reference
     ?match ?comment ?propertyType
    WHERE {
        ?property a ?propertyType.
        FILTER (?propertyType IN (owl:ObjectProperty, owl:DatatypeProperty ) )
        OPTIONAL {?property rdfs:domain ?class }.
        OPTIONAL {?property rdfs:range ?type }.
        OPTIONAL {?property rdfs:label ?name }.
        OPTIONAL {?property rdfs:comment ?description} .
        OPTIONAL {?property owl:maxCardinality ?maxCount} .
        OPTIONAL {?property owl:minCardinality ?minCount} .
        FILTER (!isBlank(?property))
        FILTER (!bound(?type) || !isBlank(?type))
        FILTER (!bound(?class) || !isBlank(?class))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "en"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
        BIND(IF(bound(?minCount), ?minCount, 0) AS ?minCount)
        BIND(IF(bound(?maxCount), ?maxCount, 1) AS ?maxCount)
        BIND(?property AS ?reference)
    }
    """

    raw_df = parse_raw_properties_dataframe(cast(list[tuple], list(graph.query(query.replace("en", language)))))
    if raw_df.empty:
        return []

    # group values and clean up
    processed_df = clean_up_properties(raw_df)

    # make compliant
    processed_df = make_properties_compliant(processed_df, importer="OWL")

    # drop column _property_type, which was a helper column:
    processed_df.drop(columns=["_property_type"], inplace=True)

    return processed_df.to_dict(orient="records")
