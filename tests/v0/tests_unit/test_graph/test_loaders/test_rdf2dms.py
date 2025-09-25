import pytest
from cognite.client.data_classes.data_modeling import ViewList

from cognite.neat.v0.core._client.data_classes.statistics import (
    CountLimitPair,
    InstanceCountsLimits,
    ProjectStatsAndLimits,
)
from cognite.neat.v0.core._client.testing import monkeypatch_neat_client
from cognite.neat.v0.core._constants import DMS_INSTANCE_LIMIT_MARGIN
from cognite.neat.v0.core._data_model.importers import SubclassInferenceImporter
from cognite.neat.v0.core._data_model.models import PhysicalDataModel
from cognite.neat.v0.core._data_model.models.conceptual._verified import (
    ConceptualDataModel,
)
from cognite.neat.v0.core._data_model.transformers._converters import (
    ToCompliantEntities,
)
from cognite.neat.v0.core._instances.loaders import DMSLoader, InstanceSpaceLoader
from cognite.neat.v0.core._issues import IssueList
from cognite.neat.v0.core._issues.errors import WillExceedLimitError
from cognite.neat.v0.core._store import NeatInstanceStore
from tests.v0.data import GraphData


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

        loader = DMSLoader(
            dms_rules,
            info_rules,
            store,
            InstanceSpaceLoader(instance_space=GraphData.car.INSTANCE_SPACE).space_by_instance_uri,
        )

        loaded = loader.load(stop_on_exception=True)

        instances_expected = {inst.external_id: inst.dump() for inst in GraphData.car.INSTANCES}
        instances_actual = {inst.external_id: inst.dump() for inst in loaded}

        assert dict(sorted(instances_expected.items())) == dict(sorted(instances_actual.items()))

    def test_load_car_example_instance_limit_reached(
        self, car_case: tuple[PhysicalDataModel, ConceptualDataModel, NeatInstanceStore]
    ) -> None:
        dms_rules, info_rules, store = car_case

        with monkeypatch_neat_client() as client:
            client.iam.verify_capabilities.return_value = []
            client.data_modeling.views.retrieve.return_value = ViewList(GraphData.car.CAR_MODEL.views)
            client.instance_statistics.project.return_value = ProjectStatsAndLimits(
                project="neat-project",
                spaces=CountLimitPair(40, 100),
                containers=CountLimitPair(100, 1000),
                views=CountLimitPair(1000, 10_000),
                data_models=CountLimitPair(10, 100),
                instances=InstanceCountsLimits(
                    nodes=4_000_000,
                    edges=750_000,
                    soft_deleted_nodes=0,
                    soft_deleted_edges=0,
                    soft_deleted_instances_limit=10_000_000,
                    instances_limit=5_000_000,
                ),
                container_properties=CountLimitPair(5_000, 25_000),
                concurrent_read_limit=8,
                concurrent_write_limit=4,
                concurrent_delete_limit=2,
            )

            loader = DMSLoader(
                dms_rules,
                info_rules,
                store,
                InstanceSpaceLoader(instance_space=GraphData.car.INSTANCE_SPACE).space_by_instance_uri,
                client,
            )

        with pytest.raises(WillExceedLimitError) as excinfo:
            _ = loader.load_into_cdf(client)

        assert excinfo.value == WillExceedLimitError("instances", 6, "neat-project", 250_000, DMS_INSTANCE_LIMIT_MARGIN)
