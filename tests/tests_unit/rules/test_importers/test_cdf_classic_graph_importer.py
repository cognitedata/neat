import pytest

from cognite.neat.rules.importers._cdf_classic import CDFClassicGraphImporter
from cognite.neat.store import NeatGraphStore
from tests.data import classic_windfarm


@pytest.fixture(scope="session")
def loaded_store() -> NeatGraphStore:
    store = NeatGraphStore.from_oxi_store()
    for extractor in classic_windfarm.create_extractors():
        store.write(extractor)
    return store


class TestCDFClassicGraphImporter:
    def test_to_rules(self, loaded_store: NeatGraphStore) -> None:
        importer = CDFClassicGraphImporter(loaded_store)
        rules = importer.to_rules()
        assert rules.rules
