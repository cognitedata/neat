import pytest
from cognite.client import CogniteClient

from cognite.neat.rules.exporters import DMSExporter
from cognite.neat.rules.importers import ExcelImporter
from cognite.neat.rules.models._rules import DMSRules, RoleTypes
from tests.config import DOC_KNOWLEDGE_ACQUISITION_TUTORIAL


@pytest.fixture(scope="session")
def alice_rules() -> DMSRules:
    filepath = DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "cdf-dms-architect-alice.xlsx"

    excel_importer = ExcelImporter(filepath)

    return excel_importer.to_rules(role=RoleTypes.dms_architect)


class TestDMSExporters:
    def test_export_to_cdf_dry_run(self, cognite_client: CogniteClient, alice_rules: DMSRules):
        rules: DMSRules = alice_rules

        exporter = DMSExporter(rules)

        uploaded = exporter.export_to_cdf(cognite_client, dry_run=True)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        assert uploaded_by_name["containers"].total == len(rules.containers)
        assert uploaded_by_name["views"].total == len(rules.views)
        assert uploaded_by_name["data_models"].total == 1
        assert uploaded_by_name["spaces"].total == 1

    def test_export_to_cdf(self, cognite_client: CogniteClient, alice_rules: DMSRules):
        rules: DMSRules = alice_rules

        exporter = DMSExporter(rules)

        uploaded = exporter.export_to_cdf(cognite_client, dry_run=False)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        assert uploaded_by_name["containers"].total == len(rules.containers)
        assert uploaded_by_name["containers"].failed == 0

        assert uploaded_by_name["views"].total == len(rules.views)
        assert uploaded_by_name["views"].failed == 0

        assert uploaded_by_name["data_models"].total == 1
        assert uploaded_by_name["data_models"].failed == 0

        assert uploaded_by_name["spaces"].total == 1
        assert uploaded_by_name["spaces"].failed == 0
