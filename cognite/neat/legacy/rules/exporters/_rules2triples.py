from pathlib import Path

from rdflib.term import Node

from cognite.neat.legacy.rules.models.rules import Rules

from ._base import BaseExporter


class TripleExporter(BaseExporter[list[tuple[Node, Node, Node]]]):
    """
    Exporter for transformation rules instances sheet to RDF triples
    """

    def _export_to_file(self, filepath: Path) -> None:
        raise NotImplementedError("Export to file not implemented")

    def export(self) -> list[tuple[Node, Node, Node]]:
        return get_instances_as_triples(self.rules)


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
