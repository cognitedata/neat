from rdflib import Namespace

from cognite.neat._graph.extractors import IODDExtractor

from ._prune_graph import AttachPropertyFromTargetToSource, PruneDanglingNodes

IODD = Namespace("http://www.io-link.com/IODD/2010/10/")


class IODDAttachPropertyFromTargetToSource(AttachPropertyFromTargetToSource):
    _need_changes = frozenset(
        {
            str(IODDExtractor.__name__),
        }
    )

    def __init__(self):
        super().__init__(
            target_node_type=IODD.TextObject,
            target_property=IODD.value,
            delete_target_node=True,
            namespace=IODD,
        )


class IODDPruneDanglingNodes(PruneDanglingNodes):
    _need_changes = frozenset({str(IODDExtractor.__name__), str(IODDAttachPropertyFromTargetToSource.__name__)})

    def __init__(self):
        super().__init__(node_prune_types=[IODD.TextObject])
