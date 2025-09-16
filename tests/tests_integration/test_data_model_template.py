from pathlib import Path

import yaml
from cognite.client import CogniteClient
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from tests.data import SchemaData

RESERVED_PROPERTIES = frozenset(
    {
        "created_time",
        "deleted_time",
        "edge_id",
        "extensions",
        "external_id",
        "last_updated_time",
        "node_id",
        "project-id",
        "project_group",
        "seq",
        "space",
        "version",
        "tg_table_name",
        "start_node",
        "end_node",
    }
)


class TestDataModelTemplate:
    def test_create_extension_template_new_endpoint(
        self, cognite_client: CogniteClient, tmp_path: Path, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client)
        output_path = tmp_path / "extension_template.xlsx"
        neat.data_model.template.expand(SchemaData.Conceptual.only_concepts_xlsx, output_path)
        assert output_path.exists()
        neat.read.excel(output_path)

        model_str = neat.to.yaml(format="neat")

        model_dict = yaml.safe_load(model_str)

        data_regression.check(model_dict)

    def test_create_extension_template(
        self, cognite_client: CogniteClient, tmp_path: Path, data_regression: DataRegressionFixture
    ) -> None:
        neat = NeatSession(cognite_client)
        output_path = tmp_path / "extension_template.xlsx"
        neat.template.expand(SchemaData.Conceptual.only_concepts_xlsx, output_path)
        assert output_path.exists()
        neat.read.excel(output_path)

        model_str = neat.to.yaml(format="neat")

        model_dict = yaml.safe_load(model_str)

        data_regression.check(model_dict)

    def test_create_extension_template_broken(
        self, cognite_client: CogniteClient, tmp_path: Path, data_regression: DataRegressionFixture
    ) -> None:
        """
        Test to validate the behavior when field is invalid in the Excel sheet. # noqa
        The broken_concepts.xlsx example has only one property, which is invalid.
        Neat should inform the end user what/where is the  when using neat.inspect
        """

        neat = NeatSession(cognite_client)
        output_path = tmp_path / "extension_template_broken.xlsx"
        neat.template.expand(SchemaData.Conceptual.broken_concepts_xlsx, output_path)

        error = neat.inspect.issues()

        assert error["NeatIssue"][0] == "PropertyValueError"
