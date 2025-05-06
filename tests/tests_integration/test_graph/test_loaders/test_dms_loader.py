import pytest
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType
from rdflib import RDF

from cognite.neat import NeatSession
from cognite.neat.core._client import NeatClient
from cognite.neat.core._constants import DEFAULT_NAMESPACE
from cognite.neat.core._graph.loaders import DMSLoader
from cognite.neat.core._rules.importers import InferenceImporter
from cognite.neat.core._store import NeatGraphStore
from tests.data import GraphData


@pytest.fixture()
def deployed_car_model(cognite_client: CogniteClient) -> dm.DataModelId:
    car = GraphData.car
    cognite_client.data_modeling.spaces.apply([dm.SpaceApply(s) for s in [car.MODEL_SPACE, car.INSTANCE_SPACE]])
    cognite_client.data_modeling.instances.apply(car.NODE_TYPES)
    cognite_client.data_modeling.containers.apply(car.CONTAINERS)
    write_model = car.CAR_MODEL.as_write()
    created = cognite_client.data_modeling.data_models.apply(write_model)
    yield created.as_id()


@pytest.fixture()
def car_store() -> NeatGraphStore:
    car = GraphData.car
    store = NeatGraphStore.from_memory_store()
    store.add_rules(car.get_care_rules())

    for triple in car.TRIPLES:
        store.dataset.add(triple)

    rules = InferenceImporter.from_graph_store(store).to_rules().rules.as_verified_rules()
    store.add_rules(rules)

    return store


class TestDMSLoader:
    @pytest.mark.skip("This test needs to be rewritten and test data updated!")
    def test_load_car_example(
        self, neat_client: NeatClient, deployed_car_model: dm.DataModelId, car_store: NeatGraphStore
    ) -> None:
        loader = DMSLoader.from_data_model_id(neat_client, deployed_car_model, car_store, GraphData.car.INSTANCE_SPACE)

        result = loader.load_into_cdf(neat_client, dry_run=False)

        assert len(result) == 4

        assert sum(item.success for item in result) == len(GraphData.car.INSTANCES)

    def test_trigger_api_read_view_max_list_size_issue(self, neat_client: NeatClient) -> None:
        expected_limits = {
            "CogniteFile.assets": 1200,
            "CogniteAsset.path": 100,
            "CogniteTimeSeries.assets": 1200,
            "CogniteActivity.assets": 1200,
        }
        neat = NeatSession(neat_client)
        neat.read.examples.core_data_model()
        dms_rules = neat._state.rule_store.last_verified_dms_rules
        info_rules = neat._state.rule_store.last_verified_information_rules
        info_rules.metadata.physical = dms_rules.metadata.identifier
        dms_rules.sync_with_info_rules(info_rules)

        # Adding some triples to
        namespace = DEFAULT_NAMESPACE
        triples = [
            (namespace[f"My{view.view.external_id}"], RDF.type, namespace[view.view.external_id])
            for view in dms_rules.views
        ]
        for triple in triples:
            neat._state.instances.store.dataset.add(triple)
        # Link triples to schema.
        for cls_ in info_rules.classes:
            cls_.instance_source = namespace[cls_.class_.suffix]

        loader = DMSLoader(
            dms_rules,
            info_rules,
            neat._state.instances.store,
            "sp_instance_space",
            client=neat_client,
        )
        iterations, _ = loader._create_view_iterations()

        actual_limits: dict[str, int] = {}
        for iteration in iterations:
            if iteration.view is None:
                continue
            for prop_id, prop in iteration.view.properties.items():
                if not isinstance(prop, dm.MappedProperty):
                    continue
                if not isinstance(prop.type, ListablePropertyType):
                    continue
                if prop.type.max_list_size:
                    actual_limits[f"{iteration.view.external_id}.{prop_id}"] = prop.type.max_list_size
        assert actual_limits == expected_limits
