import datetime

import yaml
from cognite.client import CogniteClient
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from cognite.neat.v0.core._data_model.catalog import classic_model
from cognite.neat.v0.core._data_model.models.entities._single_value import ViewEntity
from tests.v0.data import SchemaData


class TestDataModelPrepare:
    def test_prefix_dms_rules_entities(
        self, cognite_client: CogniteClient, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client)
        neat.read.examples.pump_example()

        # Hack to ensure deterministic output
        rules = neat._state.data_model_store.last_verified_physical_data_model
        rules.metadata.created = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")
        rules.metadata.updated = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")

        neat.prepare.data_model.prefix("NeatINC")

        rules_str = neat.to.yaml(format="neat")

        rules_dict = yaml.safe_load(rules_str)
        data_regression.check({"rules": rules_dict})

    def test_prefix_info_rules_entities(
        self, cognite_client: CogniteClient, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client)

        neat.read.excel(classic_model)

        # Hack to ensure deterministic output
        rules = neat._state.data_model_store.last_verified_conceptual_data_model
        rules.metadata.created = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")
        rules.metadata.updated = datetime.datetime.fromisoformat("2024-09-19T00:00:00Z")

        neat.prepare.data_model.prefix("NeatINC")

        rules_str = neat.to.yaml(format="neat")

        rules_dict = yaml.safe_load(rules_str)
        data_regression.check(
            {
                "rules": rules_dict,
            }
        )

    def test_standardize_space_and_version(
        self, cognite_client: CogniteClient, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client)

        neat.read.excel(SchemaData.Physical.mixed_up_version_xlsx)

        neat.prepare.data_model.standardize_space_and_version()

        rules_str = neat.to.yaml(format="neat")

        rules_dict = yaml.safe_load(rules_str)
        data_regression.check(
            {
                "rules": rules_dict,
            }
        )

        rules = neat._state.data_model_store.last_verified_physical_data_model

        for view in rules.views:
            assert view.view.space == rules.metadata.space
            assert view.view.version == rules.metadata.version

        for property_ in rules.properties:
            assert property_.view.space == rules.metadata.space
            assert property_.view.version == rules.metadata.version

            if isinstance(property_.value_type, ViewEntity):
                assert property_.value_type.space == rules.metadata.space
                assert property_.value_type.version == rules.metadata.version
