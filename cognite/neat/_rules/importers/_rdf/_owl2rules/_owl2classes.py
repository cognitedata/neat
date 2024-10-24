from typing import cast

from rdflib import Graph

from cognite.neat._rules.importers._rdf._shared import (
    clean_up_classes,
    make_classes_compliant,
    parse_raw_classes_dataframe,
)


def parse_owl_classes(graph: Graph, language: str = "en") -> list[dict]:
    """Parse owl classes from graph to pandas dataframe.

    Args:
        graph: Graph containing owl classes
        language: Language to use for parsing, by default "en"

    Returns:
        Dataframe containing owl classes

    !!! note "Compliant OWL classes"
        This makes the method very opinionated, but results in a compliant classes.
    """

    query = """
        SELECT ?class ?name ?description ?parentClass ?reference ?match ?comment
        WHERE {
        ?class a owl:Class .
        OPTIONAL {?class rdfs:subClassOf ?parentClass }.
        OPTIONAL {?class rdfs:label ?name }.
        OPTIONAL {?class rdfs:comment ?description} .
        FILTER (!isBlank(?class))
        FILTER (!bound(?parentClass) || !isBlank(?parentClass))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "en"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
        BIND(?class AS ?reference)
    }
    """

    # create raw dataframe

    raw_df = parse_raw_classes_dataframe(cast(list[tuple], list(graph.query(query.replace("en", language)))))
    if raw_df.empty:
        return []

    # group values and clean up
    processed_df = clean_up_classes(raw_df)

    # make compliant
    processed_df = make_classes_compliant(processed_df, importer="OWL")

    # Make Parent Class list elements into string joined with comma
    processed_df["Parent Class"] = processed_df["Parent Class"].apply(
        lambda x: ", ".join(x) if isinstance(x, list) and x else None
    )

    return processed_df.dropna(axis=0, how="all").replace(float("nan"), None).to_dict(orient="records")
