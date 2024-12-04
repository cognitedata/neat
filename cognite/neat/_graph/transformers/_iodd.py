from rdflib import Namespace

from cognite.neat._graph.extractors import IODDExtractor

from ._prune_graph import PruneDanglingNodes, TwoHopFlattener

IODD = Namespace("http://www.io-link.com/IODD/2010/10/")


class IODDTwoHopFlattener(TwoHopFlattener):
    _need_changes = frozenset(
        {
            str(IODDExtractor.__name__),
        }
    )

    def __init__(self):
        super().__init__(
            destination_node_type=IODD.TextObject,
            namespace=IODD,
            value_property_name="value",
            delete_connecting_node=True,
        )


class IODDPruneDanglingNodes(PruneDanglingNodes):
    _need_changes = frozenset({str(IODDExtractor.__name__), str(IODDTwoHopFlattener.__name__)})

    def __init__(self):
        super().__init__(node_prune_types=[IODD.TextObject])
