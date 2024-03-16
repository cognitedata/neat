from typing import cast

import pytest
from cognite.client import CogniteClient

from cognite.neat.rules.exporters import DMSExporter
from cognite.neat.rules.importers import ExcelImporter
from cognite.neat.rules.models._rules import DMSRules, InformationRules, RoleTypes
from cognite.neat.rules.models._rules.base import SheetList
from cognite.neat.rules.models._rules.dms_schema import PipelineSchema
from cognite.neat.rules.models._rules.information_rules import (
    InformationClass,
    InformationMetadata,
    InformationProperty,
)
from cognite.neat.utils.cdf_loaders import RawTableLoader
from tests.config import DOC_KNOWLEDGE_ACQUISITION_TUTORIAL


@pytest.fixture(scope="session")
def alice_rules() -> DMSRules:
    filepath = DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "cdf-dms-architect-alice.xlsx"

    excel_importer = ExcelImporter(filepath)

    return excel_importer.to_rules(errors="raise", role=RoleTypes.dms_architect)


@pytest.fixture(scope="session")
def table_example() -> InformationRules:
    return InformationRules(
        metadata=InformationMetadata(
            schema_="complete",
            prefix="sp_table_example",
            namespace="http://neat.org",
            name="The Table Example from Integration Test",
            version="1",
            description="Integration test for populate and retrieve data",
            created="2024-03-16T17:40:00Z",
            updated="2024-03-16T17:40:00Z",
            creator=["Anders"],
        ),
        properties=SheetList[InformationProperty](
            data=[
                InformationProperty(
                    class_="Table",
                    property_="color",
                    value_type="string",
                    min_count=0,
                    max_count=1.0,
                ),
                InformationProperty(
                    class_="Table",
                    property_="height",
                    value_type="float",
                    min_count=1,
                    max_count=1,
                ),
                InformationProperty(
                    class_="Table",
                    property_="width",
                    value_type="float",
                    min_count=1,
                    max_count=1,
                ),
                InformationProperty(
                    class_="Table",
                    property_="on",
                    value_type="Item",
                    min_count=0,
                    max_count=float("inf"),
                ),
                InformationProperty(
                    class_="Item",
                    property_="name",
                    value_type="string",
                    min_count=1,
                    max_count=1,
                ),
                InformationProperty(
                    class_="Item",
                    property_="category",
                    value_type="string",
                    min_count=0,
                    max_count=1,
                ),
            ]
        ),
        classes=SheetList[InformationClass](
            data=[
                InformationClass(class_="Table", name="Table"),
                InformationClass(class_="Item", name="Item"),
            ]
        ),
    )


class TestDMSExporters:
    def test_export_to_cdf_dry_run(self, cognite_client: CogniteClient, alice_rules: DMSRules):
        rules: DMSRules = alice_rules

        exporter = DMSExporter()

        uploaded = exporter.export_to_cdf(cognite_client, rules, dry_run=True)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        assert uploaded_by_name["containers"].total == len(rules.containers)
        assert uploaded_by_name["views"].total == len(rules.views)
        assert uploaded_by_name["data_models"].total == 1
        assert uploaded_by_name["spaces"].total == 1

    def test_export_to_cdf(self, cognite_client: CogniteClient, alice_rules: DMSRules):
        rules: DMSRules = alice_rules

        exporter = DMSExporter(existing_handling="force")

        uploaded = exporter.export_to_cdf(cognite_client, rules, dry_run=False)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        assert uploaded_by_name["containers"].total == len(rules.containers)
        assert uploaded_by_name["containers"].failed == 0

        assert uploaded_by_name["views"].total == len(rules.views)
        assert uploaded_by_name["views"].failed == 0

        assert uploaded_by_name["data_models"].total == 1
        assert uploaded_by_name["data_models"].failed == 0

        assert uploaded_by_name["spaces"].total == 1
        assert uploaded_by_name["spaces"].failed == 0

    def test_export_pipeline_populate_and_retrieve_data(
        self, cognite_client: CogniteClient, table_example: InformationRules
    ) -> None:
        exporter = DMSExporter(existing_handling="force", export_pipeline=True, standardize_casing=True)
        schema = cast(PipelineSchema, exporter.export(table_example))

        uploaded = list(exporter.export_to_cdf(cognite_client, table_example, dry_run=False))

        assert uploaded
        table_loader = RawTableLoader(cognite_client)
        existing_tables = table_loader.retrieve(schema.raw_tables.as_ids())
        missing_tables = set(schema.raw_tables.as_ids()) - set(existing_tables.as_ids())
        assert not missing_tables, f"Missing RAW tables: {missing_tables}"
