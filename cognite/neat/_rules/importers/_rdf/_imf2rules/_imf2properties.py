from typing import cast

from rdflib import Graph

from cognite.neat._rules.importers._rdf._shared import (
    clean_up_properties,
    make_properties_compliant,
    parse_raw_properties_dataframe,
)


def parse_imf_to_properties(graph: Graph, language: str = "en") -> list[dict]:
    """Parse IMF elements from RDF-graph and extract properties to pandas dataframe.

    Args:
        graph: Graph containing imf elements
        language: Language to use for parsing, by default "en"

    Returns:
        List of dictionaries containing properties extracted from IMF elements

    !!! note "IMF Compliance"
        The IMF elements are expressed in RDF, primarily using SHACL and OWL. To ensure
        that the resulting properties are compliant with CDF, similar validation checks
        as in the OWL ontology importer are applied.

        For the IMF-types more of the compliance logic is placed directly in the SPARQL
        query. Among these are the creation of class and property names not starting
        with a number, ensuring property types as well as default cardinality boundraries.

        IMF-attributes are considered both classes and properties. This kind of punning
        is necessary to capture additional information carried by attributes. They carry,
        among other things, a set of relationsships to reference terms, units of measure,
        and qualifiers that together make up the meaning of the attribute. These references
        are listed as additional properties with default values.
    """

    query = """
    SELECT DISTINCT ?class ?property ?name ?description ?valueType ?minCount ?maxCount ?default ?reference
    ?match ?comment ?propertyType
    WHERE
    {
        # Finding IMF-blocks and terminals
        {
            VALUES ?classType { imf:BlockType imf:TerminalType }
            ?imfClass a ?classType ;
                sh:property ?propertyShape .
                ?propertyShape sh:path ?imfProperty .

            OPTIONAL { ?imfProperty skos:prefLabel ?name . }
            OPTIONAL { ?imfProperty skos:definition | skos:description ?description . }
            OPTIONAL { ?imfProperty rdfs:range ?range . }
            OPTIONAL { ?imfProperty a ?type . }
            OPTIONAL { ?propertyShape sh:minCount ?minCardinality} .
            OPTIONAL { ?propertyShape sh:maxCount ?maxCardinality} .
            OPTIONAL { ?propertyShape sh:hasValue ?defualt . }
            OPTIONAL { ?propertyShape sh:class | sh:qualifiedValueShape/sh:class ?valueShape .}
        }
        UNION
        # Finding the IMF-attribute types
        {
            ?imfClass a imf:AttributeType ;
                ?imfProperty ?default .

            # The following information is used to describe the attribute when it is connected to a block or a terminal
            # and not duplicated here.
            # Note: Bug in PCA has lead to the use non-existing term skos:description. This will be replaced
            # with the correct skos:definition in the near future, so both terms are included here.
            FILTER(?imfProperty != rdf:type && ?imfProperty != skos:prefLabel &&
                ?imfProperty != skos:defintion && ?imfProperty != skos:description)
        }

        # Finding the last segment of the class IRI
        BIND(STR(?imfClass) AS ?classString)
        BIND(REPLACE(?classString, "^.*[/#]([^/#]*)$", "$1") AS ?tempClassSegment)
        BIND(REPLACE(?tempClassSegment, "-", "_") AS ?classSegment)
        BIND(IF(CONTAINS(?classString, "imf/"), CONCAT("IMF_", ?classSegment) , ?classSegment) AS ?class)


        # Finding the last segment of the property IRI
        BIND(STR(?imfProperty) AS ?propertyString)
        BIND(REPLACE(?propertyString, "^.*[/#]([^/#]*)$", "$1") AS ?tempPropertySegment)
        BIND(REPLACE(?tempPropertySegment, "-", "_") AS ?propertySegment)
        BIND(IF(CONTAINS(?propertyString, "imf/"), CONCAT("IMF_", ?propertySegment) , ?propertySegment) AS ?property)

        # Set the value type for the property based on sh:class, sh:qualifiedValueType or rdfs:range
        BIND(IF(BOUND(?valueShape), ?valueShape, IF(BOUND(?range) , ?range , ?valueShape)) AS ?valueIriType)

        # Finding the last segment of value types
        BIND(STR(?valueIriType) AS ?valueTypeString)
        BIND(REPLACE(?valueTypeString, "^.*[/#]([^/#]*)$", "$1") AS ?tempValueTypeSegment)
        BIND(REPLACE(?tempValueTypeSegment, "-", "_") AS ?valueTypeSegment)
        BIND(IF(CONTAINS(?valueTypeString, "imf/"), CONCAT("IMF_", ?valueTypeSegment) , ?valueTypeSegment)
            AS ?valueType)

        # Helper variable to set owl datatype- or object-property if this is not already set.
        BIND(IF( EXISTS {?imfProperty a ?tempPropertyType . FILTER(?tempPropertyType = owl:DatatypeProperty) },
            owl:DatatypeProperty,
            owl:ObjectProperty
            )
        AS ?propertyType)

        # Assert cardinality values if they do not exist
        BIND(IF(BOUND(?minCardinality), ?minCardinality, 0) AS ?minCount)
        BIND(IF(BOUND(?maxCardinality), ?maxCardinality, 1) AS ?maxCount)

        # Rebind the IRI of the IMF-attribute to the ?reference variable to align with dataframe column headers
        # This is solely for readability, the ?imfClass could have been returnered directly instead of ?reference
        BIND(?imfProperty AS ?reference)

        FILTER (!isBlank(?property))
        FILTER (!bound(?class) || !isBlank(?class))
        FILTER (!bound(?name) || LANG(?name) = "" || LANGMATCHES(LANG(?name), "en"))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
    }
    """

    raw_df = parse_raw_properties_dataframe(cast(list[tuple], list(graph.query(query.replace("en", language)))))
    if raw_df.empty:
        return []

    # group values and clean up
    processed_df = clean_up_properties(raw_df)

    # make compliant
    processed_df = make_properties_compliant(processed_df, importer="IMF")

    # drop column _property_type, which was a helper column:
    processed_df.drop(columns=["_property_type"], inplace=True)

    return processed_df.to_dict(orient="records")
