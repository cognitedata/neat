from cognite.neat.core._data_model.analysis import RulesAnalysis
from cognite.neat.core._data_model.importers import InferenceImporter
from cognite.neat.core._instances.examples import nordic44_knowledge_graph
from cognite.neat.core._instances.extractors import RdfFileExtractor
from cognite.neat.core._instances.transformers._value_type import SplitMultiValueProperty
from cognite.neat.core._store import NeatGraphStore


def test_split_multi_value_property():
    store = NeatGraphStore.from_oxi_local_store()
    extractor = RdfFileExtractor(nordic44_knowledge_graph, base_uri="http://nordic44.com/")
    store.write(extractor)

    store.transform(SplitMultiValueProperty())

    rules = InferenceImporter.from_graph_store(store).to_rules().rules.as_verified_rules()
    assert len(RulesAnalysis(rules).multi_value_properties) == 0
