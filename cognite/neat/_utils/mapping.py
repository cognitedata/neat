from collections.abc import Iterable

from rdflib import Literal, Namespace, URIRef

from cognite.neat._rules.models.information import InformationClass, InformationProperty


def create_type_mapping(
    classes: Iterable[InformationClass], namespace: Namespace
) -> dict[URIRef | Literal, URIRef | Literal]:
    """Creates a mapping of types to new types.

    Args:
        classes: The classes to map.
        namespace: The namespace to use for the mapping.

    Returns:
        A mapping of types to new types.
    """
    return {namespace[cls.name]: namespace[cls.class_.suffix] for cls in classes if cls.name}


def create_predicate_mapping(classes: Iterable[InformationProperty], namespace: Namespace) -> dict[URIRef, URIRef]:
    raise NotImplementedError()
