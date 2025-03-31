from collections.abc import Iterable

import pytest
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
