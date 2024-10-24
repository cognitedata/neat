from rdflib import Graph

from cognite.neat._rules.analysis import InformationAnalysis
from cognite.neat._rules.models._rdfpath import RDFPath, SingleProperty
from cognite.neat._rules.models.information import InformationRules

from ._base import BaseTransformer


class ReduceHopTraversal(BaseTransformer):
    """ReduceHopTraversal is a transformer that reduces the number of hops to direct connection."""

    ...


class AddSelfReferenceProperty(BaseTransformer):
    description: str = "Adds property that contains id of reference to all references of given class in Rules"
    _use_only_once: bool = True
    _need_changes = frozenset({})
    _ref_template: str = """SELECT ?s WHERE {{?s a <{type_}>}}"""

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

            for (reference,) in graph.query(self._ref_template.format(type_=namespace[suffix])):  # type: ignore [misc]
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
