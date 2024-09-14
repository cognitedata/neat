import pytest

from cognite.neat.graph.extractors import (
    AssetsExtractor,
    DataSetExtractor,
    EventsExtractor,
    FilesExtractor,
    LabelsExtractor,
    RelationshipsExtractor,
    SequencesExtractor,
    TimeSeriesExtractor,
)
from cognite.neat.rules.importers import CDFClassicGraphImporter
from cognite.neat.store import NeatGraphStore
from tests.data import classic_windfarm


@pytest.fixture(scope="session")
def loaded_store() -> NeatGraphStore:
    store = NeatGraphStore.from_oxi_store()
    for extractor in [
        DataSetExtractor(classic_windfarm.DATASETS),
        AssetsExtractor(classic_windfarm.ASSETS),
        RelationshipsExtractor(classic_windfarm.RELATIONSHIPS),
        TimeSeriesExtractor(classic_windfarm.TIME_SERIES),
        SequencesExtractor(classic_windfarm.SEQUENCES),
        FilesExtractor(classic_windfarm.FILES),
        LabelsExtractor(classic_windfarm.LABELS),
        EventsExtractor(classic_windfarm.EVENTS),
    ]:
        store.write(extractor)
    return store


class TestCDFClassicGraphImporter:
    def test_to_rules(self, loaded_store: NeatGraphStore) -> None:
        importer = CDFClassicGraphImporter(loaded_store)
        rules = importer.to_rules()
        assert rules.rules
