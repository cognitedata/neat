import pytest
import yaml
from cognite.client import CogniteClient
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
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
        assert not issues

        neat.prepare.data_model.to_data_product(("sp_my_space", "MyProduct", "v1"), org_name="")

        exported_yaml_str = neat.to.yaml()
        exported_rules = yaml.safe_load(exported_yaml_str)
        assert len(exported_rules["properties"]) == len(view.properties) + 1

        data_regression.check(exported_rules)
