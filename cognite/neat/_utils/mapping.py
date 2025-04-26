from collections.abc import Iterable

from rdflib import Literal, Namespace, URIRef

from cognite.neat._rules.models.information import InformationClass, InformationProperty


def create_type_mapping(
    classes: Iterable[InformationClass], namespace: Namespace
) -> dict[URIRef | Literal, URIRef | Literal]:
    raise NotImplementedError()


def create_predicate_mapping(classes: Iterable[InformationProperty], namespace: Namespace) -> dict[URIRef, URIRef]:
    raise NotImplementedError()
