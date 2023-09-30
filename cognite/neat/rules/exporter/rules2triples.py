from cognite.neat.rules.models import TransformationRules
from rdflib.term import Node


def get_instances_as_triples(transformation_rules: TransformationRules) -> list[tuple[Node, Node, Node]]:
    """
    Converts transformation rules instances sheet to RDF triples

    Args:
        transformation_rules: An instance of TransformationRules pydantic class

    Returns:
        List of triples provided as tuples

    """
    if transformation_rules.instances:
        return [(instance.instance, instance.property_, instance.value) for instance in transformation_rules.instances]  # type: ignore[misc]
    return []
