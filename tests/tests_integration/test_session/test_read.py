import tempfile

import pytest
import yaml
from cognite.client import CogniteClient
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from cognite.neat._rules.catalog import hello_world_pump
from tests import data


class TestRead:
    @pytest.mark.freeze_time("2024-11-22")
    def test_read_model_referencing_core(
        self, cognite_client: CogniteClient, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(client=cognite_client)
        # The CogniteDescribable view is referenced in the REFERENCING_CORE model read below.
        # The data product should lookup the describable properties and include them.
        view = cognite_client.data_modeling.views.retrieve(("cdf_cdm", "CogniteDescribable", "v1"))[0]

        neat.read.yaml(data.REFERENCING_CORE, format="toolkit")

        issues = neat.verify()
        assert not issues.has_errors

        neat.prepare.data_model.to_data_product(("sp_my_space", "MyProduct", "v1"), org_name="")

        exported_yaml_str = neat.to.yaml()
        exported_rules = yaml.safe_load(exported_yaml_str)
        assert (
            # CogniteDescribable + 1 extra in REFERENCING_CORE
            len(exported_rules["properties"]) == len(view.properties) + 1
        )

        data_regression.check(exported_rules)

    def test_read_pump_hello_world(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(client=cognite_client)

        neat.read.excel(hello_world_pump)

        issues = neat.verify()
        neat.prepare.data_model.include_referenced()

        assert not issues.has_errors

    def test_store_read_neat_session(self):
        neat = NeatSession()

        _ = neat.read.rdf.examples.nordic44

        with tempfile.NamedTemporaryFile(suffix=".zip") as session_file:
            neat.to.session(session_file.name)

            neat2 = NeatSession()
            neat2.read.session(session_file.name)

            assert (neat2._state.instances.store.graph - neat._state.instances.store.graph).serialize() == "\n"
