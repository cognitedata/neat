import re
from typing import cast

from rdflib import Graph, URIRef

from cognite.neat._rules.analysis import InformationAnalysis
from cognite.neat._rules.models._rdfpath import (
    Hop,
    RDFPath,
    SelfReferenceProperty,
    SingleProperty,
    Traversal,
)
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._rules.models.information import InformationProperty, InformationRules
from cognite.neat._utils.collection_ import most_occurring_element

from ._shared import Triple, hop2property_path

_QUERY_TEMPLATE = """CONSTRUCT {{ {graph_template} }}
                     WHERE {{     {bind_instance_id}
                                  {graph_pattern}
                     }}"""


def build_construct_query(
    class_: ClassEntity,
    graph: Graph,
    rules: InformationRules,
    properties_optional: bool = True,
    instance_id: URIRef | None = None,
) -> str | None:
    """Builds a CONSTRUCT query for a given class and rules and optionally filters by class instances.

    Args:
        class_ : The class entity for which the query is generated.
        graph : The graph containing instances of classes.
        rules : The information rules to use for query generation.
        properties_optional : Whether to make all properties optional. Defaults to True.
        class_instances : List of class instances to filter by. Defaults to None (no filter, return all instances).

    Returns:
        str: CONSTRUCT query.

    !!! note "On CONSTRUCT Query"
        CONSTRUCT query is composed of two parts: graph template and graph pattern.
        Graph template is used the shape of instance acquired using graph pattern.
        This allows us to create a new graph with the new shape without actually modifying
        the original graph, or creating new instances.

        The CONSTRUCT query is far less forgiving than the SELECT query. It will not return
        anything if one of the properties that define the "shape" of the class instance is missing.
        This is the reason why there is an option to make all properties optional, so that
        the query will return all instances that have at least one property defined.
    """

    if (
        transformations := InformationAnalysis(rules)
        .class_property_pairs(only_rdfpath=True, consider_inheritance=True)
        .get(class_, None)
    ):
        templates, patterns = to_construct_triples(
            graph, list(transformations.values()), rules.prefixes, properties_optional
        )

        return _QUERY_TEMPLATE.format(
            bind_instance_id=(f"BIND(<{instance_id}> AS ?instance)" if instance_id else ""),
            graph_template="\n".join(triples2sparql_statement(templates)),
            graph_pattern="\n".join(triples2sparql_statement(patterns)),
        )

    else:
        return None


def to_construct_triples(
    graph: Graph,
    transformations: list[InformationProperty],
    prefixes: dict,
    properties_optional: bool = True,
) -> tuple[list[Triple], list[Triple]]:
    """Converts transformations of a class to CONSTRUCT triples which are used to generate CONSTRUCT query

    Args:
        graph: Graph containing instances of classes (used for property inference for hops)
        transformations : List of transformations to use to form triples
        prefixes : Dictionary of prefixes for namespaces
        properties_optional : Flag indicating if properties should be optional. Defaults to True.

    Returns:
        tuple: Tuple of triples that define graph template and graph pattern parts of CONSTRUCT query


    !!! note "Purely inherited transformations"
        Assumption that neat makes is that in case of purely inherited transformations
        we will type instance with class to which transformation belongs to.

        Otherwise we will type instance with class that is most occurring in non-inherited
        transformations.

    """
    # TODO: Add handling of UNIONs in rules

    templates = []
    patterns = []
    non_inherited_starting_rdf_types = []

    for transformation in transformations:
        traversal = cast(RDFPath, transformation.transformation).traversal

        # keeping track of starting rdf types of non-inherited transformations/properties
        if isinstance(traversal, Traversal) and not transformation.inherited:
            non_inherited_starting_rdf_types.append(traversal.class_.id)

        graph_template_triple = Triple(
            subject="?instance",
            predicate=f"{transformation.class_.prefix}:{transformation.property_}",
            object=f'?{re.sub(r"[^_a-zA-Z0-9/_]", "_", str(transformation.property_).lower())}',
            optional=False,
        )
        templates.append(graph_template_triple)

        # use case AllReferences: binding instance to certain rdf property
        if isinstance(traversal, SelfReferenceProperty):
            graph_pattern_triple = Triple(
                subject="BIND(?instance",
                predicate="AS",
                object=f"{graph_template_triple.object})",
                optional=False,
            )

        # use case SingleProperty: simple property traversal
        elif isinstance(traversal, SingleProperty):
            graph_pattern_triple = Triple(
                subject=graph_template_triple.subject,
                predicate=traversal.property.id,
                object=graph_template_triple.object,
                optional=(True if properties_optional else not transformation.is_mandatory),
            )

        # use case Hop: property traversal with multiple hops turned into property path
        # see: https://www.oxfordsemantic.tech/faqs/what-is-a-property-path
        elif isinstance(traversal, Hop):
            graph_pattern_triple = Triple(
                subject="?instance",
                predicate=hop2property_path(graph, traversal, prefixes),
                object=graph_template_triple.object,
                optional=(True if properties_optional else not transformation.is_mandatory),
            )

        # other type of rdfpaths are skipped
        else:
            continue

        patterns.append(graph_pattern_triple)

    # Add first triple for graph pattern stating type of object
    # we use most occurring here to pull out most occurring rdf type of the starting
    # node of the transformation, or the class itself to which the transformation is
    # defined for.
    # This is safeguard in case there are multiple classes in the graph pattern
    patterns.insert(
        0,
        Triple(
            subject="?instance",
            predicate="a",
            object=(
                most_occurring_element(non_inherited_starting_rdf_types)
                if non_inherited_starting_rdf_types
                else str(transformation.class_)
            ),
            optional=False,
        ),
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
