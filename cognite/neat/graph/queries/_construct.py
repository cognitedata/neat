import re
from typing import cast

from rdflib import Graph, URIRef

from cognite.neat.rules.analysis import InformationArchitectRulesAnalysis
from cognite.neat.rules.models._rdfpath import (
    AllReferences,
    Hop,
    RDFPath,
    SingleProperty,
    Traversal,
)
from cognite.neat.rules.models.entities import ClassEntity
from cognite.neat.rules.models.information import InformationProperty, InformationRules
from cognite.neat.utils.utils import most_occurring_element

from ._shared import Triple, hop2property_path


def build_construct_query(
    class_: ClassEntity,
    graph: Graph,
    rules: InformationRules,
    properties_optional: bool = True,
    class_instances: list[URIRef] | None = None,
) -> str | None:
    """Builds a CONSTRUCT query for a given class and rules and optionally filters by class instances.

    Args:
        class_ : The class entity for which the query is generated.
        graph : The graph containing instances of classes.
        rules : The information rules to use for query generation.
        properties_optional : Whether to make all properties optional. Defaults to True.
        class_instances : List of class instances to filter by. Defaults to None (no filter, return all instances).

    Returns:
        str: The CONSTRUCT query.

    Notes:
        The CONSTRUCT query is far less forgiving than the SELECT query. It will not return
        anything if one of the properties that define the "shape" of the class instance is missing.
        This is the reason why there is an option to make all properties optional, so that
        the query will return all instances that have at least one property defined.
    """
    if (
        transformations := InformationArchitectRulesAnalysis(rules)
        .class_property_pairs(only_rdfpath=True, consider_inheritance=True)
        .get(class_, None)
    ):
        query_template = "CONSTRUCT {graph_template\n}\n\nWHERE {graph_pattern\ninsert_filter} ORDER BY ?instance"
        query_template = add_filter(class_instances, query_template)

        templates, patterns = to_construct_triples(
            graph, list(transformations.values()), rules.prefixes, properties_optional
        )

        graph_template = "\n           ".join(triples2sparql_statement(templates))
        graph_pattern = "\n       ".join(triples2sparql_statement(patterns))

        return query_template.replace("graph_template", graph_template).replace("graph_pattern", graph_pattern)
    else:
        return None


def add_filter(class_instances, query_template):
    if class_instances:
        class_instances_formatted = [f"<{instance}>" for instance in class_instances]
        query_template = query_template.replace(
            "insert_filter", f"\n\nFILTER (?instance IN ({', '.join(class_instances_formatted)}))"
        )
    else:
        query_template = query_template.replace("insert_filter", "")
    return query_template


def to_construct_triples(
    graph: Graph, transformations: list[InformationProperty], prefixes: dict, properties_optional: bool = True
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

    for transformation in transformations:
        traversal = cast(RDFPath, transformation.transformation).traversal

        if isinstance(traversal, Traversal) and not transformation.inherited:
            class_ids.append(traversal.class_.id)

        graph_template_triple = Triple(
            subject="?instance",
            predicate=f"{transformation.class_.prefix}:{transformation.property_}",
            object=f'?{re.sub(r"[^_a-zA-Z0-9/_]", "_", str(transformation.property_).lower())}',
            optional=False,
        )
        templates.append(graph_template_triple)

        # AllReferences should not be "optional" since we are creating their values
        # by binding them to certain property
        if isinstance(traversal, AllReferences):
            graph_pattern_triple = Triple(
                subject="BIND(?instance", predicate="AS", object=f"{graph_template_triple.object})", optional=False
            )

        elif isinstance(traversal, SingleProperty):
            graph_pattern_triple = Triple(
                subject=graph_template_triple.subject,
                predicate=traversal.property.id,
                object=graph_template_triple.object,
                optional=True if properties_optional else not transformation.is_mandatory,
            )

        elif isinstance(traversal, Hop):
            graph_pattern_triple = Triple(
                subject="?instance",
                predicate=hop2property_path(graph, traversal, prefixes),
                object=graph_template_triple.object,
                optional=True if properties_optional else not transformation.is_mandatory,
            )
        else:
            continue

        patterns.append(graph_pattern_triple)

    # add first triple for graph pattern stating type of object
    # we use most occurring here to pull out most occurring class id as type
    # this is safeguard in case there are multiple classes in the graph pattern
    patterns.insert(
        0, Triple(subject="?instance", predicate="a", object=most_occurring_element(class_ids), optional=False)
    )

    return templates, patterns


def triples2sparql_statement(triples: list[Triple]):
    return [
        (
            f"OPTIONAL {{ {triple.subject} {triple.predicate} {triple.object} . }}"
            if triple.optional
            else f"{triple.subject} {triple.predicate} {triple.object} ."
        )
        for triple in triples
    ]
