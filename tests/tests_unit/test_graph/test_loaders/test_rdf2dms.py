import pytest

from cognite.neat._graph.loaders import DMSLoader
from cognite.neat._issues import IssueList
from cognite.neat._rules.importers import SubclassInferenceImporter
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.transformers._converters import (
    ToCompliantEntities,
)
from cognite.neat._store import NeatGraphStore
from tests.data import car


@pytest.fixture()
def car_case() -> tuple[DMSRules, InformationRules, NeatGraphStore]:
    store = NeatGraphStore.from_oxi_local_store()

    for triple in car.TRIPLES:
        store.dataset.add(triple)
    info_rules = (
        SubclassInferenceImporter(IssueList(), store.dataset, data_model_id=("sp_example_car", "CarModel", "1"))
        .to_rules()
        .rules
    )

    info_rules = ToCompliantEntities().transform(info_rules.as_verified_rules())

    dms_rules = car.get_car_dms_rules()

    # needs conversion to DMS rules as well
    return dms_rules, info_rules, store


class TestDMSLoader:
    def test_load_car_example(self, car_case: tuple[DMSRules, InformationRules, NeatGraphStore]) -> None:
        dms_rules, info_rules, store = car_case

        loader = DMSLoader(dms_rules, info_rules, store, car.INSTANCE_SPACE)

        loaded = loader.load(stop_on_exception=True)

        instances_expected = {inst.external_id: inst.dump() for inst in car.INSTANCES}
        instances_actual = {inst.external_id: inst.dump() for inst in loaded}

        assert dict(sorted(instances_expected.items())) == dict(sorted(instances_actual.items()))
