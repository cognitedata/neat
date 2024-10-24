from cognite.neat._graph.examples import nordic44_knowledge_graph
from cognite.neat._graph.extractors import RdfFileExtractor
from cognite.neat._graph.transformers._value_type import SplitMultiValueProperty
from cognite.neat._rules.analysis import InformationAnalysis
from cognite.neat._rules.importers import InferenceImporter
from cognite.neat._rules.transformers import ImporterPipeline
from cognite.neat._store import NeatGraphStore


def test_split_multi_value_property():
    store = NeatGraphStore.from_oxi_store()
    extractor = RdfFileExtractor(nordic44_knowledge_graph, base_uri="http://nordic44.com/")
    store.write(extractor)

    store.transform(SplitMultiValueProperty())

    rules = ImporterPipeline.verify(InferenceImporter.from_graph_store(store))
    assert len(InformationAnalysis(rules).multi_value_properties) == 0
