import sys
from collections.abc import Iterable
from typing import ClassVar, cast

from pydantic import BaseModel, ConfigDict, Field
from rdflib import Graph, Literal, Namespace
from rdflib.term import URIRef

from cognite.neat.constants import PREFIXES
from cognite.neat.rules.models._rdfpath import (
    Hop,
    Step,
)
from cognite.neat.utils.utils import remove_namespace, uri_to_short_form

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class Triple(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True, arbitrary_types_allowed=True, strict=False, extra="allow"
    )

    subject: str | URIRef
    predicate: str | URIRef
    object: str | URIRef | Literal | None = None
    optional: bool = Field(
        description="Indicates whether a triple is optional, used when building SPARQL query",
        default=False,
    )

    @classmethod
    def from_rdflib_triple(cls, triple: tuple[URIRef, URIRef, URIRef | Literal]) -> Self:
        return cls(subject=triple[0], predicate=triple[1], object=triple[2])


def generate_prefix_header(prefixes: dict[str, Namespace] = PREFIXES) -> str:
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


def get_predicate_id(
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

    query = query.replace("insertPrefixes", generate_prefix_header(prefixes))
    final_query = query.replace("subjectTypeID", subject_type_id).replace("objectTypeID", object_type_id)
    res = list(cast(tuple, graph.query(final_query)))

    if len(res) != 1:
        raise ValueError("Subject and Object must have exactly 1 relation!")

    return res[0][0]


def hop2property_path(graph: Graph, hop: Hop, prefixes: dict[str, Namespace]) -> str:
    """Converts hop to property path string

    Parameters
    ----------
    graph : Graph
        Graph containing instances of classes
    hop : Hop
        Hop to convert
    prefixes : dict[str, Namespace]
        Dictionary of prefixes to use for compression and predicate querying

    Returns
    -------
    str
        Property path string for hop traversal (e.g. ^rdf:type/rdfs:subClassOf)
    """

    # setting previous step to origin, as we are starting from there
    previous_step = Step(class_=hop.class_, direction="origin")

    # add triples for all steps until destination
    property_path = ""
    for current_step in hop.traversal:
        sub_entity, obj_entity = (
            (current_step, previous_step) if current_step.direction == "source" else (previous_step, current_step)
        )

        predicate_raw = get_predicate_id(graph, sub_entity.class_.id, obj_entity.class_.id, prefixes)

        predicate = uri_to_short_form(predicate_raw, prefixes)

        predicate = f"^{predicate}" if current_step.direction == "source" else predicate
        property_path += f"{predicate}/"

        previous_step = current_step

    if previous_step.property:
        return property_path + previous_step.property.id
    else:
        # removing "/" at the end of property path if there is no property at the end
        return property_path[:-1]


def triples2dictionary(triples: Iterable[tuple[URIRef, URIRef, str | URIRef]]) -> dict[URIRef, dict[str, list[str]]]:
    """Converts list of triples to dictionary"""
    dictionary: dict[URIRef, dict[str, list[str]]] = {}
    for triple in triples:
        id_: str
        property_: str
        value: str
        uri: URIRef

        id_, property_, value = remove_namespace(*triple)  # type: ignore[misc]
        uri = triple[0]

        if uri not in dictionary:
            dictionary[uri] = {"external_id": [id_]}

        if property_ not in dictionary[uri]:
            dictionary[uri][property_] = [value]
        else:
            dictionary[uri][property_].append(value)
    return dictionary
