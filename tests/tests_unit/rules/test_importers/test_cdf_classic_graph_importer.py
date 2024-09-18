import pytest

from cognite.neat.constants import CLASSIC_CDF_NAMESPACE
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
from cognite.neat.rules.importers._cdf_classic import CDFClassicGraphImporter
from cognite.neat.store import NeatGraphStore
from tests.data import classic_windfarm


@pytest.fixture(scope="session")
def loaded_store() -> NeatGraphStore:
    store = NeatGraphStore.from_oxi_store()
    for extractor in [
        DataSetExtractor(classic_windfarm.DATASETS, namespace=CLASSIC_CDF_NAMESPACE),
        AssetsExtractor(classic_windfarm.ASSETS, namespace=CLASSIC_CDF_NAMESPACE),
        RelationshipsExtractor(classic_windfarm.RELATIONSHIPS, namespace=CLASSIC_CDF_NAMESPACE),
        TimeSeriesExtractor(classic_windfarm.TIME_SERIES, namespace=CLASSIC_CDF_NAMESPACE),
        SequencesExtractor(classic_windfarm.SEQUENCES, namespace=CLASSIC_CDF_NAMESPACE),
        FilesExtractor(classic_windfarm.FILES, namespace=CLASSIC_CDF_NAMESPACE),
        LabelsExtractor(classic_windfarm.LABELS, namespace=CLASSIC_CDF_NAMESPACE),
        EventsExtractor(classic_windfarm.EVENTS, namespace=CLASSIC_CDF_NAMESPACE),
    ]:
        store.write(extractor)
    return store


class TestCDFClassicGraphImporter:
    def test_to_rules(self, loaded_store: NeatGraphStore) -> None:
        importer = CDFClassicGraphImporter(loaded_store)
        rules = importer.to_rules()
        assert rules.rules
