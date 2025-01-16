import pytest
from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import DataModelId

from cognite.neat._rules.importers import DMSImporter, ExcelImporter
from cognite.neat._rules.models import DataModelType, DMSRules, InformationRules
from tests.config import DOC_RULES


@pytest.fixture(scope="session")
def alice_rules() -> DMSRules:
    filepath = DOC_RULES / "cdf-dms-architect-alice.xlsx"

    excel_importer = ExcelImporter(filepath)

    return excel_importer.to_rules().rules.as_verified_rules()


@pytest.fixture(scope="session")
def alice_data_model_id(alice_rules: DMSRules) -> DataModelId:
    return alice_rules.metadata.as_data_model_id()


@pytest.fixture(scope="session")
def olav_rules() -> DMSRules:
    filepath = DOC_RULES / "dms-analytics-olav.xlsx"

    excel_importer = ExcelImporter(filepath)

    return excel_importer.to_rules().rules.as_verified_rules()


@pytest.fixture(scope="session")
def olav_data_model_id(olav_rules: DMSRules) -> DataModelId:
    return olav_rules.metadata.as_data_model_id()


@pytest.mark.skip("These models depend on the exporter tests running, which are currently failing.")
class TestDMSImporter:
    def test_import_alice_from_cdf(self, cognite_client: CogniteClient, alice_data_model_id: DataModelId):
        dms_exporter = DMSImporter.from_data_model_id(cognite_client, alice_data_model_id)

        rules = dms_exporter.to_rules().rules.as_verified_rules()

        assert isinstance(rules, InformationRules)
        assert rules.metadata.data_model_type is DataModelType.enterprise

    def test_import_olav_from_cdf(
        self, cognite_client: CogniteClient, olav_data_model_id: DataModelId, alice_data_model_id: DataModelId
    ):
        dms_importer = DMSImporter.from_data_model_id(cognite_client, olav_data_model_id, alice_data_model_id)

        assert dms_importer.schema.referenced_spaces(include_indirect_references=False) == {olav_data_model_id.space}, (
            "The direct reference should be the data model space."
        )

        rules = dms_importer.to_rules().rules.as_verified_rules()

        assert isinstance(rules, DMSRules)
        assert rules.metadata.as_data_model_id() == olav_data_model_id
        assert isinstance(rules.reference, DMSRules)
        assert rules.reference.metadata.as_data_model_id() == alice_data_model_id
