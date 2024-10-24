from rdflib import XSD, Graph, URIRef

from cognite.neat._constants import UNKNOWN_TYPE
from cognite.neat._graph.queries import Queries
from cognite.neat._utils.rdf_ import remove_namespace_from_uri

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
                                FILTER (datatype(?o) = <{object_uri}>)

                                }}"""

    _unknown_property_template: str = """SELECT ?s ?o WHERE {{

                                ?s a <{subject_uri}> .
                                ?s <{property_uri}> ?o .
                                FILTER NOT EXISTS {{ ?o a ?objectType }}
                                }}"""

    def transform(self, graph: Graph) -> None:
        # handle multi value type object properties
        for subject_uri, property_uri, value_types in Queries(graph).multi_value_type_property():
            for value_type_uri in value_types:
                _args = {
                    "subject_uri": subject_uri,
                    "property_uri": property_uri,
                    "object_uri": value_type_uri,
                }

                # Case 1: Unknown value type
                if value_type_uri == UNKNOWN_TYPE:
                    iterator = graph.query(self._unknown_property_template.format(**_args))

                # Case 2: Datatype value type
                elif value_type_uri.startswith(str(XSD)):
                    iterator = graph.query(self._datatype_property_template.format(**_args))

                # Case 3: Object value type
                else:
                    iterator = graph.query(self._object_property_template.format(**_args))

                for s, o in iterator:  # type: ignore [misc]
                    graph.remove((s, property_uri, o))
                    new_property = URIRef(f"{property_uri}_{remove_namespace_from_uri(value_type_uri)}")
                    graph.add((s, new_property, o))
