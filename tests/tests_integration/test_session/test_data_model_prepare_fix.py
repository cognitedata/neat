import datetime

import yaml
from cognite.client import CogniteClient
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from cognite.neat._rules.catalog import classic_model


class TestDataModelPrepare:
    def test_prefix_dms_rules_entities(
        self, cognite_client: CogniteClient, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client)
        neat.read.excel.examples.pump_example()

        # Hack to ensure deterministic output
        rules = neat._state.rule_store.last_verified_dms_rules
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

    def test_prefix_info_rules_entities(
        self, cognite_client: CogniteClient, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client)

        neat.read.excel(classic_model)

        # Hack to ensure deterministic output
        rules = neat._state.rule_store.last_verified_information_rules
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
