from rdflib import Graph, Namespace
from rdflib.term import URIRef

from cognite.neat.core.configuration import PREFIXES
from cognite.neat.core.rules.rules import (
    AllProperties,
    AllReferences,
    Hop,
    SingleProperty,
    Traversal,
    Triple,
    parse_traversal,
)


def _generate_prefix_header(prefixes: dict[str, Namespace] = PREFIXES) -> str:
    """Generate prefix header which is added to SPARQL query and allows for shorten query statements

    Parameters
    ----------
    prefixes : dict
        Dict containing prefix - namespace pairs, default PREFIXES

    Returns
    -------
    str
        Prefix header
    """
    return "".join(f"PREFIX {key}:<{value}>\n" for key, value in prefixes.items())


def _get_predicate_id(
    graph: Graph, subject_type_id: str, object_type_id: str, prefixes: dict[str, Namespace] = PREFIXES
) -> URIRef:
    """Returns predicate (aka property) URI (i.e., ID) that connects subject and object

    Parameters
    ----------
    graph : Graph
        Data model graph or data model instance (aka knowledge graph)
    subject_type_id : str
        ID of subject type (aka subject class)
    object_type_id : str
        ID of object type (aka object class)
    prefixes : dict, optional
        Dict containing prefix - namespace pairs, default PREFIXES

    Returns
    -------
    URIRef
        ID of predicate (aka property) connecting subject and object
    """
    query = """

        SELECT ?predicateTypeID
        WHERE {
            ?subjectInstanceID a subjectTypeID .
            ?objectInstanceID a objectTypeID .
            ?subjectInstanceID ?predicateTypeID ?objectInstanceID .
        } LIMIT 1"""

    query = query.replace("insertPrefixes", _generate_prefix_header(prefixes))
    final_query = query.replace("subjectTypeID", subject_type_id).replace("objectTypeID", object_type_id)
    res = list(graph.query(final_query))

    if len(res) != 1:
        raise ValueError("Subject and Object must have exactly 1 relation!")

    return res[0][0]


def _get_direct_mapping_triples(subject, predicate) -> list[Triple]:
    return [Triple(subject, predicate, "?object")]


def _get_all_references_mapping_triples(object) -> list[Triple]:
    return [Triple("?subject", "a", object)]


def _get_entire_object_mapping(subject) -> list[Triple]:
    return [Triple(subject, "*")]


def _get_hop_triples(graph, path: Hop, prefixes) -> list[Triple]:
    triples = [Triple("?subject", "a", path.origin.class_.id)]
    previous_step = path.origin

    # add triples for all steps until destination
    for curret_step in path.traversal:
        sub_entity, obj_entity = (
            (curret_step, previous_step) if curret_step.direction == "source" else (previous_step, curret_step)
        )

        predicate = _get_predicate_id(graph, sub_entity.class_.id, obj_entity.class_.id, prefixes)

        # if this is first step after origin
        if previous_step.class_.id == path.origin.class_.id:
            if curret_step.direction == "source":
                sub, obj = f"?{sub_entity.class_.name}ID", "?subject"
            else:
                sub, obj = "?subject", f"?{obj_entity.class_.name}ID"

        # Any other step after hoping from origin to first step
        else:
            sub = f"?{sub_entity.class_.name}ID"
            obj = f"?{obj_entity.class_.name}ID"

        triples.append(Triple(sub, predicate, obj))
        previous_step = curret_step

    if previous_step.property:
        triples.extend(
            [
                Triple(f"?{previous_step.class_.name}ID", "a", previous_step.class_.id),
                Triple(f"?{previous_step.class_.name}ID", previous_step.property.id, "?object"),
                Triple("?predicate", "a", previous_step.property.id),
            ]
        )
    else:
        if previous_step.direction == "source":
            triples[-1].subject = "?object"
        else:
            triples[-1].object = "?object"
        triples.append(Triple("?object", "a", previous_step.class_.id))

    return triples


def _get_path_triples(graph: Graph, traversal: Traversal, prefixes: dict[str, Namespace] = PREFIXES) -> list[Triple]:
    """Creates triples subject-predicate-object from declarative graph traversal path

    Parameters
    ----------
    graph : Graph
        Data model graph or data model instance (aka knowledge graph)
    traversal : Traversal
        Parsed traversal path in declarative form
    prefixes : dict, optional
        Dict containing prefix - namespace pairs, default PREFIXES

    Returns
    -------
    list
        List of triples to be consumed by SPARQL query builder
    """
    match traversal:
        case SingleProperty():
            return _get_direct_mapping_triples(traversal.class_.id, traversal.property.id)
        case AllProperties():
            return _get_entire_object_mapping(traversal.class_.id)
        case AllReferences():
            return _get_all_references_mapping_triples(traversal.class_.id)
        case Hop():
            return _get_hop_triples(graph, traversal, prefixes)
        case _:
            raise ValueError("Incorrectly set traversal path!")


BASIC_SPARQL_QUERY_TEMPLATE = """insertPrefixes

SELECT DISTINCT ?subject ?predicate ?object
    WHERE {
query_insertions
        }"""


REFERENCES_ONLY_SPARQL_QUERY_TEMPLATE = """insertPrefixes

SELECT DISTINCT ?subject ?predicate ?object {
    {SELECT DISTINCT  ?object ?predicate {
        query_insertions
        BIND(dct:identifier AS ?predicate)}}

        BIND(?object AS ?subject)

        }"""


# This template does not work with in-memory graph, so it has been replaced with the one above
REFERENCES_ONLY_SPARQL_QUERY_TEMPLATE_OLD = """insertPrefixes

SELECT DISTINCT ?subject ?predicate ?object
    WHERE {
query_insertions
                {
                BIND(?object AS ?subject)
                BIND(dct:identifier AS ?predicate)
                }
        }"""

SINGLE_PROPERTY_SPARQL_QUERY_TEMPLATE = """insertPrefixes

SELECT DISTINCT ?subject ?predicate ?object
    WHERE {
query_insertions
                {
                BIND(property_insertion AS ?predicate)
                }
        }"""


def _generate_all_properties_query_statement(subject: str, query_template: str = BASIC_SPARQL_QUERY_TEMPLATE) -> str:
    query_insertions = "\n".join([f"\t\t?subject a {subject} .", "\t\t?subject ?predicate ?object ."])

    return query_template.replace("query_insertions", query_insertions)


def _generate_all_references_query_statement(
    object: str, query_template: str = REFERENCES_ONLY_SPARQL_QUERY_TEMPLATE
) -> str:
    query_insertions = "\n".join([f"\t\t?object a {object} ."])

    return query_template.replace("query_insertions", query_insertions)


def _generate_single_property_query_statement(
    subject: str, predicate: str, query_template: str = SINGLE_PROPERTY_SPARQL_QUERY_TEMPLATE
) -> str:
    query_insertions = "\n".join([f"\t\t?subject a {subject} .", f"\t\t?subject {predicate} ?object ."])

    return query_template.replace("query_insertions", query_insertions).replace("property_insertion", predicate)


def _generate_hop_query_statement(triples: list[Triple], query_template: str = BASIC_SPARQL_QUERY_TEMPLATE) -> str:
    terminal_triplet = triples[-1]

    query_insertions = "".join(
        f"             {triple.subject} {triple.predicate} {triple.object} .\n" for triple in triples[:-1]
    )

    # Creating terminal query statement based on whether we are query for specific
    # property of an object (first option) or object ID
    if terminal_triplet.subject == "?predicate":
        query_insertions += f"             BIND({terminal_triplet.object} AS ?predicate)\n"
    else:
        query_insertions += (
            f"             {terminal_triplet.subject} {terminal_triplet.predicate} {terminal_triplet.object} .\n"
        )
        query_insertions += "             BIND(dct:relation AS ?predicate)\n"

    return query_template.replace("query_insertions", query_insertions)


def build_sparql_query(
    graph: Graph,
    traversal_path: str | Traversal,
    prefixes: dict[str, Namespace] = PREFIXES,
    insert_prefixes: bool = False,
) -> str:
    """Builds SPARQL query based on declarative traversal path

    Parameters
    ----------
    graph : Graph
        Data model graph or data model instance (aka knowledge graph)
    traversal_path : str
        String representing graph traversal path in declarative form
    prefixes : dict, optional
        Dict containing prefix - namespace pairs, default PREFIXES

    Returns
    -------
    str
        SPARQL query
    """

    traversal = parse_traversal(traversal_path) if isinstance(traversal_path, str) else traversal_path
    triples = _get_path_triples(graph, traversal, prefixes)

    if isinstance(traversal, AllProperties):
        query = _generate_all_properties_query_statement(triples[0].subject)
    elif isinstance(traversal, AllReferences):
        query = _generate_all_references_query_statement(triples[0].object)
    elif isinstance(traversal, SingleProperty):
        query = _generate_single_property_query_statement(triples[0].subject, triples[0].predicate)
    elif isinstance(traversal, Hop):
        query = _generate_hop_query_statement(triples)
    else:
        raise ValueError("Not Supported!")

    # Replacing long URIs with short form using their prefixes
    for prefix, URI in prefixes.items():
        query = query.replace(URI, f"{prefix}:")

    return query.replace("insertPrefixes\n\n", _generate_prefix_header(prefixes) if insert_prefixes else "")
