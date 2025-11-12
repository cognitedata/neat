from pathlib import Path

import pytest
import yaml
from cognite.client import CogniteClient
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from cognite.neat.v0.core._data_model.catalog import hello_world_pump
from tests.v0.data import SchemaData


@pytest.mark.skip(reason="Legacy tests which we no longer maintain")
class TestRead:
    @pytest.mark.freeze_time("2024-11-22")
    def test_read_model_referencing_core(
        self, cognite_client: CogniteClient, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(client=cognite_client)
        # The CogniteDescribable view is referenced in the REFERENCING_CORE model read below.
        # The data product should lookup the describable properties and include them.
        view = cognite_client.data_modeling.views.retrieve(("cdf_cdm", "CogniteDescribable", "v1"))[0]

        issues = neat.read.yaml(SchemaData.NonNeatFormats.referencing_core_yamls, format="toolkit")
        assert not issues.has_errors, issues

        neat.template.data_product_model(("sp_my_space", "MyProduct", "v1"))

        exported_yaml_str = neat.to.yaml()
        exported_rules = yaml.safe_load(exported_yaml_str)
        assert (
            # CogniteDescribable + 1 extra in REFERENCING_CORE
            len(exported_rules["properties"]) == len(view.properties) + 1
        )

        data_regression.check(exported_rules)

    def test_read_cdm(self, cognite_client: CogniteClient, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(client=cognite_client)
        # The CogniteDescribable view is referenced in the REFERENCING_CORE model read below.
        # The data product should lookup the describable properties and include them.
        neat.read.cdf.data_model(("cdf_cdm", "CogniteCore", "v1"))

        exported_yaml_str = neat.to.yaml()
        exported_rules = yaml.safe_load(exported_yaml_str)

        data_regression.check(exported_rules)

    def test_read_pump_hello_world(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(client=cognite_client)

        issues = neat.read.excel(hello_world_pump)

        assert len(issues) == 0

    def test_store_read_neat_session(self, tmp_path: Path) -> None:
        neat = NeatSession()

        _ = neat.read.examples.nordic44()

        session_file = tmp_path / "session.zip"
        try:
            neat.to.session(session_file)

            neat2 = NeatSession()
            neat2.read.session(session_file)

            assert set(neat2._state.instances.store.dataset) - set(neat._state.instances.store.dataset) == set()
        finally:
            session_file.unlink()

    def test_read_pump_with_duplicates(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(client=cognite_client)
        neat.read.excel(SchemaData.Physical.pump_example_duplicated_resources_xlsx)
        assert len(neat._state.data_model_store.last_issues) == 4

    def test_data_model_views_not_in_same_space(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(client=cognite_client)
        issues = neat.read.excel(SchemaData.Physical.dm_view_space_different_xlsx)
        assert not issues.has_errors

    def test_read_core_no_warnings(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(client=cognite_client)

        issues = neat.read.examples.core_data_model()

        assert not issues.has_errors

    def test_read_classic_graph(self, cognite_client: CogniteClient) -> None:
        neat = NeatSession(client=cognite_client)

        issues = neat.read.cdf.classic.graph(root_asset_external_id="Utsira")

        assert len(issues) == 0
