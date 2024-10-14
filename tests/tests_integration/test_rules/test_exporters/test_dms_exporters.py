import itertools
from typing import cast

import pytest
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes import Row

from cognite.neat.rules.exporters import DMSExporter
from cognite.neat.rules.importers import ExcelImporter
from cognite.neat.rules.models import DMSRules, InformationRules, RoleTypes, SheetList
from cognite.neat.rules.models.dms import DMSInputRules, PipelineSchema
from cognite.neat.rules.models.information import (
    InformationClass,
    InformationMetadata,
    InformationProperty,
)
from cognite.neat.rules.transformers import ImporterPipeline, InformationToDMS
from cognite.neat.utils.cdf.loaders import RawTableLoader, TransformationLoader
from tests.config import DOC_RULES


@pytest.fixture(scope="session")
def alice_rules() -> DMSRules:
    filepath = DOC_RULES / "cdf-dms-architect-alice.xlsx"

    excel_importer = ExcelImporter(filepath)

    return ImporterPipeline.verify(excel_importer, role=RoleTypes.dms)


@pytest.fixture(scope="session")
def olav_dms_rules() -> DMSRules:
    filepath = DOC_RULES / "dms-analytics-olav.xlsx"

    excel_importer = ExcelImporter(filepath)

    return ImporterPipeline.verify(excel_importer, role=RoleTypes.dms)


@pytest.fixture(scope="session")
def olav_rebuilt_dms_rules() -> DMSRules:
    filepath = DOC_RULES / "dms-rebuild-olav.xlsx"

    excel_importer = ExcelImporter(filepath)

    return ImporterPipeline.verify(excel_importer, role=RoleTypes.dms)


@pytest.fixture(scope="session")
def svein_harald_dms_rules() -> DMSRules:
    filepath = DOC_RULES / "dms-addition-svein-harald.xlsx"

    excel_importer = ExcelImporter(filepath)

    return ImporterPipeline.verify(excel_importer, role=RoleTypes.dms)


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
            [
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
                    max_count=1,
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
            [
                InformationClass(class_="Table", name="Table"),
                InformationClass(class_="Item", name="Item"),
            ]
        ),
    )


@pytest.fixture(scope="session")
def table_example_data() -> dict[str, list[Row]]:
    return {
        "Table": [
            Row("table1", {"externalId": "table1", "color": "brown", "height": 1.0, "width": 2.0, "type": "Table"}),
            Row(
                "table2",
                {"externalId": "table2", "color": "white", "height": 1.5, "width": 3.0, "type": "Table"},
            ),
        ],
        "Item": [
            Row("item1", {"externalId": "item1", "name": "chair", "category": "furniture", "type": "Item"}),
            Row("item2", {"externalId": "item2", "name": "lamp", "category": "lighting", "type": "Item"}),
            Row("item3", {"externalId": "item3", "name": "computer", "category": "electronics", "type": "Item"}),
        ],
        "TableItem": [
            Row("table1item1", {"externalId": "table1item1", "Table": "table1", "Item": "item1"}),
            Row("table1item2", {"externalId": "table1item2", "Table": "table1", "Item": "item2"}),
            Row("table2item3", {"externalId": "table2item3", "Table": "table2", "Item": "item3"}),
        ],
    }


class TestDMSExporters:
    def test_export_alice_to_cdf_dry_run(self, cognite_client: CogniteClient, alice_rules: DMSRules):
        rules: DMSRules = alice_rules

        exporter = DMSExporter()

        uploaded = exporter.export_to_cdf_iterable(rules, cognite_client, dry_run=True)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        assert uploaded_by_name["containers"].success == len(rules.containers)
        assert uploaded_by_name["views"].success == len(rules.views)
        assert uploaded_by_name["data_models"].success == 1
        assert uploaded_by_name["spaces"].success == 1

    def test_export_alice_to_cdf(self, cognite_client: CogniteClient, alice_rules: DMSRules):
        rules: DMSRules = alice_rules

        exporter = DMSExporter(existing_handling="force")

        uploaded = exporter.export_to_cdf_iterable(rules, cognite_client, dry_run=False)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        assert uploaded_by_name["containers"].success == len(rules.containers)
        assert uploaded_by_name["containers"].failed == 0

        assert uploaded_by_name["views"].success == len(rules.views)
        assert uploaded_by_name["views"].failed == 0

        assert uploaded_by_name["data_models"].success == 1
        assert uploaded_by_name["data_models"].failed == 0

        assert uploaded_by_name["spaces"].success == 1
        assert uploaded_by_name["spaces"].failed == 0

    def test_export_pipeline_populate_and_retrieve_data(
        self, cognite_client: CogniteClient, table_example: InformationRules, table_example_data: dict[str, list[str]]
    ) -> None:
        exporter = DMSExporter(
            existing_handling="force",
            export_pipeline=True,
            instance_space="sp_table_example_data",
        )
        dms_rules = InformationToDMS().transform(table_example).rules
        schema = cast(PipelineSchema, exporter.export(dms_rules))

        # Write Pipeline to CDF
        uploaded = exporter.export_to_cdf(dms_rules, cognite_client, dry_run=False)

        # Verify Raw Tables are written
        assert uploaded
        table_loader = RawTableLoader(cognite_client)
        existing_tables = table_loader.retrieve(schema.raw_tables.as_ids())
        missing_tables = set(schema.raw_tables.as_ids()) - set(existing_tables.as_ids())
        assert not missing_tables, f"Missing RAW tables: {missing_tables}"

        # Write data to RAW tables
        db_name = schema.databases[0].name
        if not cognite_client.raw.rows.list(db_name, "TableProperties", limit=-1):
            cognite_client.raw.rows.insert(db_name, "TableProperties", table_example_data["Table"])
        if not cognite_client.raw.rows.list(db_name, "ItemProperties", limit=-1):
            cognite_client.raw.rows.insert(db_name, "ItemProperties", table_example_data["Item"])
        if not cognite_client.raw.rows.list(db_name, "Table.OnEdge", limit=-1):
            cognite_client.raw.rows.insert(db_name, "Table.OnEdge", table_example_data["TableItem"])

        # Verify Transformations are written
        transformation_loader = TransformationLoader(cognite_client)
        existing_transformations = transformation_loader.retrieve(schema.transformations.as_external_ids())
        missing_transformations = set(schema.transformations.as_external_ids()) - set(
            existing_transformations.as_external_ids()
        )
        assert not missing_transformations, f"Missing transformations: {missing_transformations}"

        # Trigger transformations (if not already triggered)
        for transformation in existing_transformations:
            if transformation.last_finished_job is None:
                # As of 16. March 2024, this must be done manually as we do not set credentials for the client
                # It is kept here to show the complete flow to populate a data model
                cognite_client.transformations.run(transformation.id, wait=True, timeout=30.0)

        # Verify data is in the data model
        views = schema.views
        table_view = next((view for view in views.values() if view.external_id == "Table"), None)
        assert table_view is not None, "Table view not found"
        table_nodes = cognite_client.data_modeling.instances.list(
            "node", space="sp_table_example_data", sources=[table_view.as_id()], limit=-1
        )
        assert len(table_nodes) == len(table_example_data["Table"])
        item_view = next((view for view in views.values() if view.external_id == "Item"), None)
        item_nodes = cognite_client.data_modeling.instances.list(
            "node", space="sp_table_example_data", sources=[item_view.as_id()], limit=-1
        )
        assert len(item_nodes) == len(table_example_data["Item"])

        table_to_item_type = cast(dm.EdgeConnectionApply, table_view.properties["on"]).type

        is_edge_type = dm.filters.Equals(
            ["edge", "type"], {"space": table_to_item_type.space, "externalId": table_to_item_type.external_id}
        )
        table_item_edges = cognite_client.data_modeling.instances.list(
            "edge", space="sp_table_example_data", filter=is_edge_type, limit=-1
        )
        assert len(table_item_edges) == len(table_example_data["TableItem"])

    def test_export_olav_dms_to_cdf(self, cognite_client: CogniteClient, olav_dms_rules: DMSRules) -> None:
        rules: DMSRules = olav_dms_rules

        exporter = DMSExporter(existing_handling="force")

        uploaded = exporter.export_to_cdf_iterable(rules, cognite_client, dry_run=False)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        assert uploaded_by_name["containers"].success == len(rules.containers)
        assert uploaded_by_name["containers"].failed == 0

        assert uploaded_by_name["views"].success == len(rules.views)
        assert uploaded_by_name["views"].failed == 0

        assert uploaded_by_name["data_models"].success == 1
        assert uploaded_by_name["data_models"].failed == 0

        assert uploaded_by_name["spaces"].success == 1
        assert uploaded_by_name["spaces"].failed == 0

    def test_export_svein_harald_dms_to_cdf(
        self, cognite_client: CogniteClient, svein_harald_dms_rules: DMSRules
    ) -> None:
        # We change the space to avoid conflicts with Alice's rules in the previous test
        dumped = svein_harald_dms_rules.dump(by_alias=True)
        new_space = "power_update"
        dumped["Metadata"]["space"] = new_space
        dumped["Last"]["Metadata"]["space"] = new_space
        reloaded = DMSInputRules.load(dumped)
        rules = reloaded.as_rules()
        schema = rules.as_schema()
        assert schema.referenced_spaces(include_indirect_references=True) == {new_space}
        exporter = DMSExporter(existing_handling="force")
        # First, we ensure that the previous version of the data model is deployed
        uploaded = exporter.export_to_cdf(rules.last, cognite_client, dry_run=False)
        failed = [entity for entity in uploaded if entity.failed]
        assert not failed, f"Failed to deploy previous version of the data model: {failed}"

        uploaded = exporter.export_to_cdf(rules, cognite_client, dry_run=False)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        assert uploaded_by_name["containers"].success == len(rules.containers)
        assert uploaded_by_name["containers"].failed == 0

        assert uploaded_by_name["views"].success == len(schema.views)
        assert uploaded_by_name["views"].failed == 0

        assert uploaded_by_name["data_models"].success == 1
        assert uploaded_by_name["data_models"].failed == 0

        assert uploaded_by_name["spaces"].success == 1
        assert uploaded_by_name["spaces"].failed == 0

    def test_export_olav_updated_dms_to_cdf(
        self, cognite_client: CogniteClient, olav_rebuilt_dms_rules: DMSRules
    ) -> None:
        # We change the space to avoid conflicts with Olav's not-updated rules in the previous test
        dumped = olav_rebuilt_dms_rules.dump(by_alias=True)
        new_solution_space = "power_analytics_update"
        new_enterprise_space = "power_update"
        dumped["Metadata"]["space"] = new_solution_space
        dumped["Last"]["Metadata"]["space"] = new_solution_space
        dumped["Reference"]["Metadata"]["space"] = new_enterprise_space
        for prop in itertools.chain(
            dumped["Properties"], dumped["Last"]["Properties"], dumped["Reference"]["Properties"]
        ):
            if prop["Reference"]:
                prop["Reference"] = prop["Reference"].replace("power", new_enterprise_space)
            if prop["Container"]:
                prop["Container"] = prop["Container"].replace("power", new_enterprise_space)
        for view in itertools.chain(dumped["Views"], dumped["Last"]["Views"], dumped["Reference"]["Views"]):
            if view["Reference"]:
                view["Reference"] = view["Reference"].replace("power", new_enterprise_space)
            if view["Implements"]:
                view["Implements"] = view["Implements"].replace("power", new_enterprise_space)
        for container in itertools.chain(
            dumped.get("Containers", []) or [],
            dumped["Last"].get("Containers", []) or [],
            dumped["Reference"].get("Containers", []) or [],
        ):
            if container["Reference"]:
                container["Reference"] = container["Reference"].replace("power", new_enterprise_space)
            if container["Constraint"]:
                container["Constraint"] = container["Constraint"].replace("power", new_enterprise_space)
            container["Container"] = container["Container"].replace("power", new_enterprise_space)
            container["Class (linage)"] = container["Class (linage)"].replace("power", new_enterprise_space)
        dumped["Last"]["Reference"] = dumped["Reference"]
        rules = DMSInputRules.load(dumped).as_rules()
        schema = rules.as_schema()
        referenced_spaces = (
            schema.referenced_spaces(True)
            | schema.last.referenced_spaces(True)
            | schema.reference.referenced_spaces(True)
        )
        assert referenced_spaces == {new_enterprise_space, new_solution_space}
        exporter = DMSExporter(existing_handling="force")
        # First, we ensure that the previous version of the data model is deployed
        uploaded = exporter.export_to_cdf(rules.last, cognite_client, dry_run=False)
        failed = [entity for entity in uploaded if entity.failed]
        assert not failed, f"Failed to deploy previous version of the data model: {failed}"

        uploaded = exporter.export_to_cdf_iterable(rules, cognite_client, dry_run=False)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        assert uploaded_by_name["containers"].success == len(schema.containers)
        assert uploaded_by_name["containers"].failed == 0

        assert uploaded_by_name["views"].success == len(schema.views)
        assert uploaded_by_name["views"].failed == 0

        assert uploaded_by_name["data_models"].success == 1
        assert uploaded_by_name["data_models"].failed == 0

        assert uploaded_by_name["spaces"].success == 1
        assert uploaded_by_name["spaces"].failed == 0
