import pytest
from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import DataModelId

from cognite.neat.rules.importers import DMSImporter, ExcelImporter
from cognite.neat.rules.models.rules import DMSRules, InformationRules, RoleTypes
from tests.config import DOC_RULES


@pytest.fixture(scope="session")
def alice_rules() -> DMSRules:
    filepath = DOC_RULES / "cdf-dms-architect-alice.xlsx"

    excel_importer = ExcelImporter(filepath)

    return excel_importer.to_rules(errors="raise", role=RoleTypes.dms_architect)


@pytest.fixture(scope="session")
def alice_data_model_id(alice_rules: DMSRules) -> DataModelId:
    return alice_rules.as_schema().data_models[0].as_id()


class TestDMSImporter:
    def test_import_from_cdf(self, cognite_client: CogniteClient, alice_data_model_id: DataModelId):
        dms_exporter = DMSImporter.from_data_model_id(cognite_client, alice_data_model_id)

        rules = dms_exporter.to_rules(errors="raise", role=RoleTypes.information_architect)

        assert isinstance(rules, InformationRules)
