from cognite.neat.v0.core._store import NeatInstanceStore


def test_provenance():
    store = NeatInstanceStore.from_memory_store()

    assert store.provenance[0].activity.used == "NeatInstanceStore.__init__"
    assert store.provenance[0].description == "Initialize graph store as Memory"
