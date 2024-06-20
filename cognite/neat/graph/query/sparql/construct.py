import re
import sys
from collections import Counter
from collections.abc import Iterable
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field
from rdflib import Graph, Literal
from rdflib.term import URIRef

from cognite.neat.rules.models._rdfpath import (
    AllReferences,
    Hop,
    SingleProperty,
    TransformationRuleType,
    Traversal,
    parse_rule,
)
from cognite.neat.rules.models.entities import ClassEntity
from cognite.neat.rules.models.information import InformationRules
from cognite.neat.utils.utils import remove_namespace

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


def build_construct_query(
    graph: Graph,
    class_: ClassEntity,
    rules: InformationRules,
    properties_optional: bool = True,
    class_instances: list[URIRef] | None = None,
) -> str:
    """Builds CONSTRUCT query for given class and rules and optionally filters by class instances

    Parameters
    ----------
    graph : Graph
        Graph containing instances of classes
    class_ : str
        Class entity for which we want to generate query
    rules : InformationRules
        InformationRules rules to use for query generation
    properties_optional : bool, optional
        Whether to make all properties optional, default True
    class_instances : list[URIRef], optional
        List of class instances to filter by, default None (no filter return all instances)

    Returns
    -------
    str
        CONSTRUCT query

    Notes
    -----
    Construct query is far less unforgiving than SELECT query, in sense that it will not return
    anything if one of the properties that define "shape" of the class instance is missing.
    This is the reason why there is option to make all properties optional, so that query will
    return all instances that have at least one property defined.

    """

    query_template = "CONSTRUCT {graph_template\n}\n\nWHERE {graph_pattern\ninsert_filter}"
    query_template = _add_filter(class_instances, query_template)

    templates, patterns = _to_construct_triples(graph, class_, rules, properties_optional)

    graph_template = "\n           ".join(_triples2sparql_statement(templates))
    graph_pattern = "\n       ".join(_triples2sparql_statement(patterns))

    return query_template.replace("graph_template", graph_template).replace("graph_pattern", graph_pattern)


def _add_filter(class_instances, query_template):
    if class_instances:
        class_instances_formatted = [f"<{instance}>" for instance in class_instances]
        query_template = query_template.replace(
            "insert_filter", f"\n\nFILTER (?subject IN ({', '.join(class_instances_formatted)}))"
        )
    else:
        query_template = query_template.replace("insert_filter", "")
    return query_template


def _to_construct_triples(
    graph: Graph, class_: ClassEntity, rules: InformationRules, properties_optional: bool = True
) -> tuple[list[Triple], list[Triple]]:
    """Converts class definition to CONSTRUCT triples which are used to generate CONSTRUCT query

    Parameters
    ----------
    graph : Graph
        Graph containing instances of classes
    class_ : str
        Class entity for which we want to generate query
    rules : InformationRules
        InformationRules rules to use for query generation

    Returns
    -------
    tuple[list[Triple],list[Triple]]
        Tuple of triples that define graph template and graph pattern parts of CONSTRUCT query
    """
    # TODO: Add handling of UNIONs in rules

    templates = []
    patterns = []

    class_ids = []
    for property_ in get_classes_with_properties(rules)[class_]:
        if property_.rule_type != TransformationRuleType.rdfpath or property_.skip_rule:
            continue
        if not isinstance(property_.rule, str):
            raise ValueError("Rule must be string!")
        traversal = parse_rule(property_.rule, property_.rule_type).traversal

        if isinstance(traversal, Traversal):
            class_ids.append(traversal.class_.id)

        graph_template_triple = Triple(
            subject="?subject",
            predicate=f"{rules.metadata.prefix}:{property_.property_id}",
            object=f'?{re.sub(r"[^_a-zA-Z0-9/_]", "_", str(property_.property_id).lower())}',
            optional=False,
        )
        templates.append(graph_template_triple)

        # AllReferences should not be "optional" since we are creating their values
        # by binding them to certain property
        if isinstance(traversal, AllReferences):
            graph_pattern_triple = Triple(
                subject="BIND(?subject", predicate="AS", object=f"{graph_template_triple.object})", optional=False
            )

        elif isinstance(traversal, SingleProperty):
            graph_pattern_triple = Triple(
                subject=graph_template_triple.subject,
                predicate=traversal.property.id,
                object=graph_template_triple.object,
                optional=True if properties_optional else not property_.is_mandatory,
            )

        elif isinstance(traversal, Hop):
            graph_pattern_triple = Triple(
                subject="?subject",
                predicate=_hop2property_path(graph, traversal, rules.prefixes),
                object=graph_template_triple.object,
                optional=True if properties_optional else not property_.is_mandatory,
            )
        else:
            continue

        patterns.append(graph_pattern_triple)

    # add first triple for graph pattern stating type of object
    patterns.insert(
        0, Triple(subject="?subject", predicate="a", object=_most_occurring_element(class_ids), optional=False)
    )

    return templates, patterns


def _most_occurring_element(list_of_elements: list):
    counts = Counter(list_of_elements)
    return counts.most_common(1)[0][0]


def _triples2sparql_statement(triples: list[Triple]):
    return [
        (
            f"OPTIONAL {{ {triple.subject} {triple.predicate} {triple.object} . }}"
            if triple.optional
            else f"{triple.subject} {triple.predicate} {triple.object} ."
        )
        for triple in triples
    ]


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
