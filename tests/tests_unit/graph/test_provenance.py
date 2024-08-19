from cognite.neat.store import NeatGraphStore


def test_provenance():
    store = NeatGraphStore.from_memory_store()

    assert store.provenance[0].activity.used == "NeatGraphStore.__init__"
    assert store.provenance[0].description == "Initialize graph store as Memory"
