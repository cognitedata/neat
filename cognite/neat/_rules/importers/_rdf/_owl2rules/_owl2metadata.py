from rdflib import Graph, Namespace

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._rules.importers._rdf._shared import make_metadata_compliant
from cognite.neat._rules.models import RoleTypes, SchemaCompleteness
from cognite.neat._utils.collection_ import remove_none_elements_from_set
from cognite.neat._utils.rdf_ import convert_rdflib_content


def parse_owl_metadata(graph: Graph) -> dict:
    """Parse owl metadata from graph to dict.

    Args:
        graph: Graph containing owl metadata

    Returns:
        Dictionary containing owl metadata

    !!! note "Compliant OWL metadata"
        This makes the method very opinionated, but results in a compliant metadata.


    """
    # TODO: Move dataframe to dict representation

    query = f"""SELECT ?namespace ?prefix ?version ?created ?updated ?title ?description ?creator ?rights ?license
    WHERE {{
        ?namespace a owl:Ontology .
        OPTIONAL {{?namespace owl:versionInfo ?version }}.
        OPTIONAL {{?namespace dcterms:creator ?creator }}.
        OPTIONAL {{?namespace <{DEFAULT_NAMESPACE.prefix}> ?prefix }}.
        OPTIONAL {{?namespace dcterms:title|rdfs:label|skos:prefLabel ?title }}.
        OPTIONAL {{?namespace dcterms:modified ?updated }}.
        OPTIONAL {{?namespace dcterms:created ?created }}.
        OPTIONAL {{?namespace dcterms:description ?description }}.
        OPTIONAL {{?namespace dcterms:rights|dc:rights ?rights }}.

        OPTIONAL {{?namespace dcterms:license|dc:license ?license }}.
        FILTER (!isBlank(?namespace))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
        FILTER (!bound(?title) || LANG(?title) = "" || LANGMATCHES(LANG(?title), "en"))
    }}
    """

    results = [{item for item in sublist} for sublist in list(zip(*graph.query(query), strict=True))]

    raw_metadata = convert_rdflib_content(
        {
            "role": RoleTypes.information,
            "schema": SchemaCompleteness.partial,
            "prefix": results[1].pop(),
            "namespace": Namespace(results[0].pop()),
            "version": results[2].pop(),
            "created": results[3].pop(),
            "updated": results[4].pop(),
            "title": results[5].pop(),
            "description": results[6].pop(),
            "creator": (
                ", ".join(remove_none_elements_from_set(results[7]))
                if remove_none_elements_from_set(results[7])
                else None
            ),
            "rights": results[8].pop(),
            "license": results[9].pop(),
        }
    )

    return make_metadata_compliant(raw_metadata)
