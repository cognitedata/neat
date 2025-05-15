import urllib.parse
from collections.abc import Iterable
from typing import overload

from rdflib import Namespace, URIRef

from cognite.neat.core._data_model.models.conceptual import Concept, ConceptualProperty


@overload
def create_type_mapping(classes: Iterable[Concept], namespace: Namespace) -> dict[URIRef, URIRef]: ...


@overload
def create_type_mapping(classes: Iterable[Concept], namespace: None = None) -> dict[str, str]: ...


def create_type_mapping(
    classes: Iterable[Concept], namespace: Namespace | None = None
) -> dict[URIRef, URIRef] | dict[str, str]:
    """Creates a mapping of types to new types.

    Args:
        classes: The classes to map.
        namespace: The namespace to use for the mapping.

    Returns:
        A mapping of types to new types.
    """
    if namespace is None:
        return {urllib.parse.quote(cls.name): cls.concept.suffix for cls in classes if cls.name}
    else:
        return {namespace[urllib.parse.quote(cls.name)]: namespace[cls.concept.suffix] for cls in classes if cls.name}


@overload
def create_predicate_mapping(
    properties: Iterable[ConceptualProperty], namespace: Namespace
) -> dict[URIRef, URIRef]: ...


@overload
def create_predicate_mapping(properties: Iterable[ConceptualProperty], namespace: None = None) -> dict[str, str]: ...


def create_predicate_mapping(
    properties: Iterable[ConceptualProperty], namespace: Namespace | None = None
) -> dict[URIRef, URIRef] | dict[str, str]:
    """Creates a mapping of predicates to new predicates."""
    if namespace is None:
        return {urllib.parse.quote(prop.name): prop.property_ for prop in properties if prop.name}
    else:
        return {namespace[urllib.parse.quote(prop.name)]: namespace[prop.property_] for prop in properties if prop.name}
