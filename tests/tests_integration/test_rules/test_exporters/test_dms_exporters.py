import itertools
from collections.abc import Iterable

import pytest
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes import Row

from cognite.neat._client import NeatClient
from cognite.neat._rules.exporters import DMSExporter
from cognite.neat._rules.importers import ExcelImporter
from cognite.neat._rules.models import DMSRules, InformationRules, SheetList
from cognite.neat._rules.models.dms import (
    DMSInputContainer,
    DMSInputMetadata,
    DMSInputProperty,
    DMSInputRules,
    DMSInputView,
)
from cognite.neat._rules.models.information import (
    InformationClass,
    InformationMetadata,
    InformationProperty,
)
from tests.config import DOC_RULES


@pytest.fixture(scope="session")
def alice_rules() -> DMSRules:
    filepath = DOC_RULES / "cdf-dms-architect-alice.xlsx"

    excel_importer = ExcelImporter(filepath)

    return excel_importer.to_rules().rules.as_verified_rules()


@pytest.fixture(scope="session")
def olav_dms_rules() -> DMSRules:
    filepath = DOC_RULES / "dms-analytics-olav.xlsx"

    excel_importer = ExcelImporter(filepath)

    return excel_importer.to_rules().rules.as_verified_rules()


@pytest.fixture(scope="session")
def olav_rebuilt_dms_rules() -> DMSRules:
    filepath = DOC_RULES / "dms-rebuild-olav.xlsx"

    excel_importer = ExcelImporter(filepath)

    return excel_importer.to_rules().rules.as_verified_rules()


@pytest.fixture(scope="session")
def svein_harald_dms_rules() -> DMSRules:
    filepath = DOC_RULES / "dms-addition-svein-harald.xlsx"

    excel_importer = ExcelImporter(filepath)

    return excel_importer.to_rules().rules.as_verified_rules()


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


@pytest.mark.skip("These models are referencing other models are thus failing to be exported. Needs another solution")
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

        exporter = DMSExporter(existing="force")

        uploaded = exporter.export_to_cdf_iterable(rules, cognite_client, dry_run=False)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        assert uploaded_by_name["containers"].success == len(rules.containers) * 2  # 2 x due to delete and create
        assert uploaded_by_name["containers"].failed == 0

        assert uploaded_by_name["views"].success == len(rules.views) * 2  # 2 x due to delete and create
        assert uploaded_by_name["views"].failed == 0

        assert uploaded_by_name["data_models"].success == 1 * 2  # 2 x due to delete and create
        assert uploaded_by_name["data_models"].failed == 0

        assert uploaded_by_name["spaces"].success == 1  # Space is not deleted
        assert uploaded_by_name["spaces"].failed == 0

    def test_export_olav_dms_to_cdf(self, cognite_client: CogniteClient, olav_dms_rules: DMSRules) -> None:
        rules: DMSRules = olav_dms_rules

        exporter = DMSExporter(existing="force")

        uploaded = exporter.export_to_cdf_iterable(rules, cognite_client, dry_run=False)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        # We have to double the amount of entities due to the delete and create
        assert uploaded_by_name["containers"].success == len(rules.containers) * 2
        assert uploaded_by_name["containers"].failed == 0

        assert uploaded_by_name["views"].success == len(rules.views) * 2
        assert uploaded_by_name["views"].failed == 0

        assert uploaded_by_name["data_models"].success == 1 * 2
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
        rules = reloaded.as_verified_rules()
        schema = rules.as_schema()
        assert schema.referenced_spaces(include_indirect_references=True) == {new_space}
        exporter = DMSExporter(existing="force")
        # First, we ensure that the previous version of the data model is deployed
        uploaded = exporter.export_to_cdf(rules.last, cognite_client, dry_run=False)
        failed = [entity for entity in uploaded if entity.failed]
        assert not failed, f"Failed to deploy previous version of the data model: {failed}"

        uploaded = exporter.export_to_cdf(rules, cognite_client, dry_run=False)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        # We have to double the amount of entities due to the delete and create
        assert uploaded_by_name["containers"].success == len(rules.containers) * 2
        assert uploaded_by_name["containers"].failed == 0

        assert uploaded_by_name["views"].success == len(schema.views) * 2
        assert uploaded_by_name["views"].failed == 0

        assert uploaded_by_name["data_models"].success == 1 * 2
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
        rules = DMSInputRules.load(dumped).as_verified_rules()
        schema = rules.as_schema()
        referenced_spaces = (
            schema.referenced_spaces(True)
            | schema.last.referenced_spaces(True)
            | schema.reference.referenced_spaces(True)
        )
        assert referenced_spaces == {new_enterprise_space, new_solution_space}
        exporter = DMSExporter(existing="force")
        # First, we ensure that the previous version of the data model is deployed
        uploaded = exporter.export_to_cdf(rules.last, cognite_client, dry_run=False)
        failed = [entity for entity in uploaded if entity.failed]
        assert not failed, f"Failed to deploy previous version of the data model: {failed}"

        uploaded = exporter.export_to_cdf_iterable(rules, cognite_client, dry_run=False)
        uploaded_by_name = {entity.name: entity for entity in uploaded}

        # We have to double the amount of entities due to the delete and create
        assert uploaded_by_name["containers"].success == len(schema.containers) * 2
        assert uploaded_by_name["containers"].failed == 0

        assert uploaded_by_name["views"].success == len(schema.views) * 2
        assert uploaded_by_name["views"].failed == 0

        assert uploaded_by_name["data_models"].success == 1 * 2
        assert uploaded_by_name["data_models"].failed == 0

        assert uploaded_by_name["spaces"].success == 1
        assert uploaded_by_name["spaces"].failed == 0


@pytest.fixture()
def existing_data_model(neat_client: NeatClient) -> Iterable[dm.DataModel]:
    space = dm.SpaceApply("neat_integration_test")
    created = neat_client.data_modeling.spaces.apply(space)
    assert created is not None
    container = dm.ContainerApply(
        space.space,
        "ExistingContainer",
        properties={
            "existing": dm.ContainerProperty(dm.data_types.Text()),
        },
        used_for="node",
    )
    created = neat_client.data_modeling.containers.apply(container)
    assert created is not None
    view = dm.ViewApply(
        space.space,
        "ExistingView",
        "v1",
        properties={"existing": dm.MappedPropertyApply(container.as_id(), "existing")},
    )
    created = neat_client.data_modeling.views.apply(view)
    assert created is not None
    data_model = dm.DataModelApply(space.space, "ExportModelMergeWithExisting", "v1", views=[view.as_id()])
    created = neat_client.data_modeling.data_models.apply(data_model)
    assert created is not None
    try:
        yield data_model
    finally:
        neat_client.data_modeling.data_models.delete(data_model.as_id())
        neat_client.data_modeling.views.delete(view.as_id())
        neat_client.data_modeling.containers.delete(container.as_id())


class TestDMSExporter:
    def test_export_model_merge_with_existing(self, existing_data_model: dm.DataModel, neat_client: NeatClient):
        space = existing_data_model.space
        rules = DMSInputRules(
            DMSInputMetadata(
                space=space,
                external_id=existing_data_model.external_id,
                version=existing_data_model.version,
                creator="doctrino",
            ),
            properties=[
                DMSInputProperty(
                    "NewView", "newProp", "text", container="ExistingContainer", container_property="newProp"
                ),
            ],
            views=[DMSInputView("NewView")],
            containers=[DMSInputContainer("ExistingContainer", used_for="node")],
        ).as_verified_rules()

        try:
            uploaded = DMSExporter(existing="update").export_to_cdf(rules, neat_client, dry_run=False)
            error_messages: list[str] = []
            for item in uploaded:
                error_messages.extend(item.error_messages)
            assert len(error_messages) == 0, error_messages

            data_model = neat_client.data_modeling.data_models.retrieve(existing_data_model.as_id()).latest_version()
            assert set(data_model.views) == {
                dm.ViewId(space, "ExistingView", "v1"),
                dm.ViewId(space, "NewView", existing_data_model.version),
            }
            container = neat_client.data_modeling.containers.retrieve((space, "ExistingContainer"))
            assert set(container.properties) == {"existing", "newProp"}
        finally:
            neat_client.data_modeling.data_models.delete(existing_data_model.as_id())
            neat_client.data_modeling.views.delete(dm.ViewId(space, "NewView", existing_data_model.version))
