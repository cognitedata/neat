from rdflib.term import Node

from cognite.neat.rules.models.rules import Rules


def get_instances_as_triples(transformation_rules: Rules) -> list[tuple[Node, Node, Node]]:
    """
    Converts transformation rules instances sheet to RDF triples

    Args:
        transformation_rules: An instance of TransformationRules pydantic class

    Returns:
        List of triples provided as tuples

    """
    if transformation_rules.instances:
        return [
            (instance.instance, instance.property_, instance.value)  # type: ignore[misc]
            for instance in transformation_rules.instances
        ]
    return []
