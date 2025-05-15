import pytest

from cognite.neat.core._data_model.importers import SubclassInferenceImporter
from cognite.neat.core._data_model.models import PhysicalDataModel
from cognite.neat.core._data_model.models.conceptual._verified import (
    ConceptualDataModel,
)
from cognite.neat.core._data_model.transformers._converters import (
    ToCompliantEntities,
)
from cognite.neat.core._instances.loaders import DMSLoader
from cognite.neat.core._issues import IssueList
from cognite.neat.core._store import NeatInstanceStore
from tests.data import GraphData


@pytest.fixture()
def car_case() -> tuple[PhysicalDataModel, ConceptualDataModel, NeatInstanceStore]:
    store = NeatInstanceStore.from_oxi_local_store()

    for triple in GraphData.car.TRIPLES:
        store.dataset.add(triple)
    info_rules = (
        SubclassInferenceImporter(
            IssueList(),
            store.dataset,
            data_model_id=("sp_example_car", "CarModel", "1"),
        )
        .to_data_model()
        .unverified_data_model
    )

    info_rules = ToCompliantEntities().transform(info_rules.as_verified_data_model())

    dms_rules = GraphData.car.get_car_dms_rules()

    # needs conversion to DMS rules as well
    return dms_rules, info_rules, store


class TestDMSLoader:
    def test_load_car_example(self, car_case: tuple[PhysicalDataModel, ConceptualDataModel, NeatInstanceStore]) -> None:
        dms_rules, info_rules, store = car_case

        loader = DMSLoader(dms_rules, info_rules, store, GraphData.car.INSTANCE_SPACE)

        loaded = loader.load(stop_on_exception=True)

        instances_expected = {inst.external_id: inst.dump() for inst in GraphData.car.INSTANCES}
        instances_actual = {inst.external_id: inst.dump() for inst in loaded}

        assert dict(sorted(instances_expected.items())) == dict(sorted(instances_actual.items()))
