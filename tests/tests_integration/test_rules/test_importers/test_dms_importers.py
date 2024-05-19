from typing import cast

import pytest
from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import DataModelId

from cognite.neat.rules.importers import DMSImporter, ExcelImporter
from cognite.neat.rules.models import DMSRules, RoleTypes
from tests.config import DOC_RULES


@pytest.fixture(scope="session")
def alice_rules() -> DMSRules:
    filepath = DOC_RULES / "cdf-dms-architect-alice.xlsx"

    excel_importer = ExcelImporter(filepath)

    return excel_importer.to_rules(errors="raise", role=RoleTypes.dms_architect)


@pytest.fixture(scope="session")
def alice_data_model_id(alice_rules: DMSRules) -> DataModelId:
    return alice_rules.metadata.as_data_model_id()


@pytest.fixture(scope="session")
def olav_rules() -> DMSRules:
    filepath = DOC_RULES / "dms-analytics-olav.xlsx"

    excel_importer = ExcelImporter(filepath)

    return excel_importer.to_rules(errors="raise", role=RoleTypes.dms_architect)


@pytest.fixture(scope="session")
def olav_data_model_id(olav_rules: DMSRules) -> DataModelId:
    return olav_rules.metadata.as_data_model_id()


class TestDMSImporter:
    def test_import_alice_from_cdf(
        self, cognite_client: CogniteClient, alice_data_model_id: DataModelId, alice_rules: DMSRules
    ):
        dms_exporter = DMSImporter.from_data_model_id(cognite_client, alice_data_model_id)
        expected = {
            "properties": sorted(
                [(prop.view.as_id(), prop.view_property) for prop in alice_rules.properties],
                key=lambda x: (*x[0].as_tuple(), x[1]),
            ),
            "views": sorted({view.view.as_id() for view in alice_rules.views}, key=lambda x: x.as_tuple()),
            "containers": sorted(
                {container.container.as_id() for container in alice_rules.containers}, key=lambda x: x.as_tuple()
            ),
        }

        imported = cast(DMSRules, dms_exporter.to_rules(errors="raise", role=RoleTypes.dms_architect))

        actual = {
            "properties": sorted(
                [(prop.view.as_id(), prop.view_property) for prop in imported.properties],
                key=lambda x: (*x[0].as_tuple(), x[1]),
            ),
            "views": sorted({view.view.as_id() for view in imported.views}, key=lambda x: x.as_tuple()),
            "containers": sorted(
                {container.container.as_id() for container in imported.containers}, key=lambda x: x.as_tuple()
            ),
        }

        assert actual == expected

    def test_import_olav_from_cdf(
        self, cognite_client: CogniteClient, olav_data_model_id: DataModelId, alice_data_model_id: DataModelId
    ):
        dms_exporter = DMSImporter.from_data_model_id(cognite_client, olav_data_model_id, alice_data_model_id)

        assert dms_exporter.root_schema.referenced_spaces(include_indirect_references=False) == {
            olav_data_model_id.space
        }, "The direct reference should be the data model space."

        rules = dms_exporter.to_rules(errors="raise", role=RoleTypes.dms_architect)

        assert isinstance(rules, DMSRules)
        assert rules.metadata.as_data_model_id() == olav_data_model_id
        assert isinstance(rules.reference, DMSRules)
        assert rules.reference.metadata.as_data_model_id() == alice_data_model_id
