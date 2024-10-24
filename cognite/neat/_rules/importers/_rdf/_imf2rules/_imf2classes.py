from typing import cast

from rdflib import Graph

from cognite.neat._rules.importers._rdf._shared import (
    clean_up_classes,
    make_classes_compliant,
    parse_raw_classes_dataframe,
)


def parse_imf_to_classes(graph: Graph, language: str = "en") -> list[dict]:
    """Parse IMF elements from RDF-graph and extract classes to pandas dataframe.

    Args:
        graph: Graph containing imf elements
        language: Language to use for parsing, by default "en"

    Returns:
        Dataframe containing imf elements

    !!! note "IMF Compliance"
        The IMF elements are expressed in RDF, primarily using SHACL and OWL. To ensure
        that the resulting classes are compliant with CDF, similar validation checks as
        in the OWL ontology importer are applied.

        For the IMF-types more of the compliance logic is placed directly in the SPARQL
        query. Among these are the creation of class name not starting with a number,
        and ensuring that all classes have a parent.

        IMF-attributes are considered both classes and properties. This kind of punning
        is necessary to capture additional information carried by attributes. They carry,
        among other things, a set of relationsships to reference terms, units of measure,
        and qualifiers that together make up the meaning of the attribute.
    """

    query = """
    SELECT ?class ?name ?description ?parentClass ?reference ?match ?comment
    WHERE {
        # Finding IMF - elements
        VALUES ?type { imf:BlockType imf:TerminalType imf:AttributeType }
        ?imfClass a ?type .
        OPTIONAL {?imfClass rdfs:subClassOf ?parent }.
        OPTIONAL {?imfClass rdfs:label | skos:prefLabel ?name }.

        # Note: Bug in PCA has lead to the use non-existing term skos:description. This will be replaced
        # with the correct skos:definition in the near future, so both terms are included here.
        OPTIONAL {?imfClass rdfs:comment | skos:definition | skos:description ?description} .

        # Finding the last segment of the class IRI
        BIND(STR(?imfClass) AS ?classString)
        BIND(REPLACE(?classString, "^.*[/#]([^/#]*)$", "$1") AS ?tempSegment)
        BIND(REPLACE(?tempSegment, "-", "_") AS ?classSegment)
        BIND(IF(CONTAINS(?classString, "imf/"), CONCAT("IMF_", ?classSegment) , ?classSegment) AS ?class)

        # Add imf:Attribute as parent class
        BIND(IF(!bound(?parent) && ?type = imf:AttributeType, imf:Attribute, ?parent) AS ?parentClass)

        # Rebind the IRI of the IMF-type to the ?reference variable to align with dataframe column headers
        # This is solely for readability, the ?imfClass could have been returned directly instead of ?reference
        BIND(?imfClass AS ?reference)

        FILTER (!isBlank(?class))
        FILTER (!bound(?parentClass) || !isBlank(?parentClass))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "en"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
    }
    """

    # create raw dataframe
    raw_df = parse_raw_classes_dataframe(cast(list[tuple], list(graph.query(query.replace("en", language)))))
    if raw_df.empty:
        return []

    # group values and clean up
    processed_df = clean_up_classes(raw_df)

    # make compliant
    processed_df = make_classes_compliant(processed_df, importer="IMF")

    # Make Parent Class list elements into string joined with comma
    processed_df["Parent Class"] = processed_df["Parent Class"].apply(
        lambda x: ", ".join(x) if isinstance(x, list) and x else None
    )

    return processed_df.dropna(axis=0, how="all").replace(float("nan"), None).to_dict(orient="records")
