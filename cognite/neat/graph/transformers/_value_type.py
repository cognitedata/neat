from typing import cast

from rdflib import XSD, Graph, URIRef

from cognite.neat.issues._base import IssueList
from cognite.neat.rules.analysis import InformationAnalysis
from cognite.neat.rules.models._rdfpath import SingleProperty
from cognite.neat.rules.models.data_types import AnyURI, DataType
from cognite.neat.rules.models.entities import (
    ClassEntity,
    MultiValueTypeInfo,
)
from cognite.neat.rules.models.information import InformationRules

from ._base import BaseTransformer


class SplitMultiValueProperty(BaseTransformer):
    description: str = (
        "SplitMultiValueProperty is a transformer that splits a "
        "multi-value property into multiple single-value properties."
    )
    _use_only_once: bool = True
    _need_changes = frozenset({})

    _object_property_template: str = """SELECT ?s ?o WHERE{{

                                ?s a <{subject_uri}> .
                                ?s <{property_uri}> ?o .
                                ?o a <{object_uri}> .

                            }}"""

    _datatype_property_template: str = """SELECT ?s ?o WHERE {{

                                ?s a <{subject_uri}> .
                                ?s <{property_uri}> ?o .
                                FILTER (datatype(?o) = <{datatype}>)

                                }}"""

    def transform(self, graph: Graph) -> None:
        rules = self._infer_rules(graph)

        class_reference_pairs = {class_.class_: class_.reference for class_ in rules.classes}

        for property_ in InformationAnalysis(rules).multi_value_properties:
            transformation = property_.transformation
            if transformation and isinstance(transformation.traversal, SingleProperty):
                traversal = transformation.traversal

                for value_type in cast(MultiValueTypeInfo, property_.value_type).types:
                    property_uri = rules.prefixes.get(traversal.property.prefix, rules.metadata.namespace)[
                        traversal.property.suffix
                    ]

                    subject_uri = rules.prefixes.get(traversal.class_.prefix, rules.metadata.namespace)[
                        traversal.class_.suffix
                    ]

                    # needs forming object_uri this way since we are also
                    # translating original rdf types to rdf types in new
                    # namespace so we need to pick the correct one which are
                    # store in class references
                    if isinstance(value_type, ClassEntity) and (
                        object_uri := class_reference_pairs.get(value_type, None)
                    ):
                        for s, o in graph.query(  # type: ignore [misc]
                            self._object_property_template.format(
                                subject_uri=subject_uri,
                                property_uri=property_uri,
                                object_uri=object_uri,
                            )
                        ):
                            graph.remove((s, property_uri, o))
                            new_property = URIRef(f"{property_uri}_{value_type.suffix}")
                            graph.add((s, new_property, o))

                    elif isinstance(value_type, DataType) and not isinstance(value_type, AnyURI):
                        for s, o in graph.query(  # type: ignore [misc]
                            self._datatype_property_template.format(
                                subject_uri=subject_uri,
                                property_uri=property_uri,
                                datatype=XSD[value_type.xsd],
                            )
                        ):
                            graph.remove((s, property_uri, o))
                            new_property = URIRef(f"{property_uri}_{value_type.xsd}")
                            graph.add((s, new_property, o))

    @classmethod
    def _infer_rules(cls, graph: Graph) -> InformationRules:
        """This is internal method inferring rules from the graph prior running the transformer."""
        from cognite.neat.rules.importers import InferenceImporter
        from cognite.neat.rules.transformers._pipelines import ImporterPipeline

        rules = cast(
            InformationRules,
            ImporterPipeline.verify(
                InferenceImporter(
                    issue_list=IssueList(title="InferenceImporter issues"),
                    graph=graph,
                    prefix="temp",
                    max_number_of_instance=-1,
                    non_existing_node_type=AnyURI(),
                )
            ),
        )

        return rules
