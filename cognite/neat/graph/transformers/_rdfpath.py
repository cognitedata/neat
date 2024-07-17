from rdflib import RDF, Graph

from cognite.neat.rules.analysis import InformationAnalysis
from cognite.neat.rules.models._rdfpath import RDFPath, SingleProperty
from cognite.neat.rules.models.information import InformationRules

from ._base import BaseTransformer


class ReduceHopTraversal(BaseTransformer):
    """ReduceHopTraversal is a transformer that reduces the number of hops to direct connection."""

    ...


class AddAllReferences(BaseTransformer):
    description: str = "Adds all references to specific property defined in Rules"
    _use_only_once: bool = True
    _need_changes = frozenset({})

    def __init__(
        self,
        rules: InformationRules,
    ):
        self.rules = rules
        self.properties = InformationAnalysis(rules).all_reference_transformations()

    def transform(self, graph: Graph) -> None:
        for property_ in self.properties:
            prefix = property_.transformation.traversal.class_.prefix
            suffix = property_.transformation.traversal.class_.suffix

            namespace = self.rules.prefixes[prefix] if prefix in self.rules.prefixes else self.rules.metadata.namespace

            for reference in graph.subjects(RDF.type, namespace[suffix]):
                graph.add(
                    (
                        reference,
                        self.rules.metadata.namespace[property_.property_],
                        reference,
                    )
                )

            traversal = SingleProperty.from_string(
                class_=property_.class_.id,
                property_=f"{self.rules.metadata.prefix}:{property_.property_}",
            )

            property_.transformation = RDFPath(traversal=traversal)
