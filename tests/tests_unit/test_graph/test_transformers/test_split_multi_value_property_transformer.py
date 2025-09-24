from cognite.neat.v0.core._data_model.analysis import DataModelAnalysis
from cognite.neat.v0.core._data_model.importers import InferenceImporter
from cognite.neat.v0.core._instances.examples import nordic44_knowledge_graph
from cognite.neat.v0.core._instances.extractors import RdfFileExtractor
from cognite.neat.v0.core._instances.transformers._value_type import SplitMultiValueProperty
from cognite.neat.v0.core._store import NeatInstanceStore


def test_split_multi_value_property():
    store = NeatInstanceStore.from_oxi_local_store()
    extractor = RdfFileExtractor(nordic44_knowledge_graph, base_uri="http://nordic44.com/")
    store.write(extractor)

    store.transform(SplitMultiValueProperty())

    rules = InferenceImporter.from_graph_store(store).to_data_model().unverified_data_model.as_verified_data_model()
    assert len(DataModelAnalysis(rules).multi_value_properties) == 0
