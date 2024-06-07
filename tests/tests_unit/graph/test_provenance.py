from cognite.neat.graph.stores import MemoryStore


def test_provenance():
    store = MemoryStore()

    assert store.provenance[0].activity.used == "MemoryStore.__init__"
