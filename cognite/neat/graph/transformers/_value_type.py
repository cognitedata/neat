from typing import cast

from rdflib import XSD, Graph, URIRef

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

    def __init__(
        self,
        rules: InformationRules,
    ):
        self.rules = rules

    def transform(self, graph: Graph) -> None:
        for property_ in InformationAnalysis(self.rules).multi_value_properties:
            transformation = property_.transformation
            if transformation and isinstance(transformation.traversal, SingleProperty):
                traversal = transformation.traversal

                for value_type in cast(MultiValueTypeInfo, property_.value_type).types:
                    property_uri = self.rules.prefixes.get(traversal.property.prefix, self.rules.metadata.namespace)[
                        traversal.property.suffix
                    ]

                    subject_uri = self.rules.prefixes.get(traversal.class_.prefix, self.rules.metadata.namespace)[
                        traversal.class_.suffix
                    ]

                    if isinstance(value_type, ClassEntity):
                        object_uri = self.rules.prefixes.get(
                            cast(str, value_type.prefix), self.rules.metadata.namespace
                        )[value_type.suffix]

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
