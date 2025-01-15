import pytest

from cognite.neat._graph.loaders import DMSLoader
from cognite.neat._rules.importers import InferenceImporter
from cognite.neat._rules.transformers import VerifyInformationRules
from cognite.neat._store import NeatGraphStore
from tests.data import car


@pytest.fixture()
def car_case() -> NeatGraphStore:
    store = NeatGraphStore.from_oxi_store()

    for triple in car.TRIPLES:
        store.dataset.add(triple)
    read_rules = InferenceImporter.from_graph_store(store).to_rules()
    rules = VerifyInformationRules().transform(read_rules)
    store.add_rules(rules)

    return store


class TestDMSLoader:
    def test_load_car_example(self, car_case: NeatGraphStore) -> None:
        loader = DMSLoader(car_case, car.CAR_MODEL, car.INSTANCE_SPACE)

        loaded = loader.load(stop_on_exception=True)

        instances_expected = {inst.external_id: inst.dump() for inst in car.INSTANCES}
        instances_actual = {inst.external_id: inst.dump() for inst in loaded}

        assert dict(sorted(instances_expected.items())) == dict(sorted(instances_actual.items()))
