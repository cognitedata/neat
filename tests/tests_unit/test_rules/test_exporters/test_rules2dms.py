import re
import zipfile
from collections import Counter
from pathlib import Path

import pytest
from cognite.client import data_modeling as dm

from cognite.neat.core._constants import (
    DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT,
    DMS_PRIMITIVE_LIST_DEFAULT_LIMIT,
)
from cognite.neat.core._data_model import importers
from cognite.neat.core._data_model.exporters import DMSExporter
from cognite.neat.core._data_model.models import ConceptualDataModel
from cognite.neat.core._data_model.models.physical import (
    PhysicalDataModel,
    UnverifiedPhysicalContainer,
    UnverifiedPhysicalDataModel,
    UnverifiedPhysicalMetadata,
    UnverifiedPhysicalProperty,
    UnverifiedPhysicalView,
)
from cognite.neat.core._data_model.transformers import (
    ConceptualToPhysical,
    VerifyAnyDataModel,
)
from cognite.neat.core._issues import catch_issues
from tests.data import SchemaData


class TestDMSExporter:
    def test_export_dms_schema_has_names_description(self, alice_rules: PhysicalDataModel) -> None:
        rules = alice_rules.model_copy(deep=True)

        # purposely setting default value for connection that should not be
        # considered when exporting DMS rules to DMS schema
        rules.properties[3].default = "Norway"

        exporter = DMSExporter()
        schema = exporter.export(rules)

        first_view = next(iter(schema.views.values()))
        assert first_view.name == "Generating Unit"
        assert first_view.description == "An asset that is creating power"
        assert first_view.properties["activePower"].name == "active power"
        assert first_view.properties["activePower"].description == "Active power of generating unit"

        first_container = next(iter(schema.containers.values()))
        assert first_container.properties["geoLocation"].default_value is None

    def test_export_dms_schema_to_zip(self, alice_rules: PhysicalDataModel, tmp_path: Path) -> None:
        exporter = DMSExporter()
        schema = exporter.export(alice_rules)
        zipfile_path = tmp_path / "test.zip"

        exporter.export_to_file(alice_rules, zipfile_path)

        counts = Counter()
        with zipfile.ZipFile(zipfile_path, "r") as zip_ref:
            for name in zip_ref.namelist():
                matches = re.search(r"[a-zA-Z0-9_].(space|datamodel|view|container|node).yaml$", name)
                counts.update([matches.group(1)])

        assert counts["space"] == len(schema.spaces)
        assert counts["datamodel"] == 1
        assert counts["view"] == len(alice_rules.views)
        assert counts["container"] == len(alice_rules.containers)
        assert counts["node"] == len(schema.node_types)

    def test_export_dms_keep_default_list_limits(self) -> None:
        model = UnverifiedPhysicalDataModel(
            metadata=UnverifiedPhysicalMetadata(
                "my_space",
                "my_model",
                "doctrino",
                "v1",
            ),
            properties=[
                UnverifiedPhysicalProperty(
                    "Asset",
                    "equipments",
                    "Equipment",
                    connection="direct",
                    max_count=DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT,
                    min_count=0,
                    container="Asset",
                    container_property="equipments",
                ),
                UnverifiedPhysicalProperty(
                    "Asset",
                    "tags",
                    "text",
                    max_count=DMS_PRIMITIVE_LIST_DEFAULT_LIMIT,
                    min_count=0,
                    container="Asset",
                    container_property="tags",
                ),
                UnverifiedPhysicalProperty("Asset", "name", "text", container="Asset", container_property="name"),
                UnverifiedPhysicalProperty(
                    "Equipment", "name", "text", container="Equipment", container_property="name"
                ),
            ],
            views=[
                UnverifiedPhysicalView("Asset"),
                UnverifiedPhysicalView("Equipment"),
            ],
            containers=[
                UnverifiedPhysicalContainer("Asset"),
                UnverifiedPhysicalContainer("Equipment"),
            ],
        )

        exporter = DMSExporter()

        exported = exporter.export(model.as_verified_data_model())

        container = exported.containers[dm.ContainerId("my_space", "Asset")]
        assert "equipments" in container.properties
        equipment_type = container.properties["equipments"].type
        assert isinstance(equipment_type, dm.data_types.ListablePropertyType)
        assert equipment_type.max_list_size == DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT

        assert "tags" in container.properties
        tags_type = container.properties["tags"].type
        assert isinstance(tags_type, dm.data_types.ListablePropertyType)
        assert tags_type.max_list_size == DMS_PRIMITIVE_LIST_DEFAULT_LIMIT


class TestImportExportDMS:
    @pytest.mark.parametrize(
        "filepath",
        [
            pytest.param(SchemaData.Physical.dms_unknown_value_type_xlsx, id="DMS source"),
            pytest.param(SchemaData.Conceptual.information_unknown_value_type_xlsx, id="Information source"),
        ],
    )
    def test_import_excel_export_dms(self, filepath: Path) -> None:
        with catch_issues() as issues:
            importer = importers.ExcelImporter(filepath)
            rules = VerifyAnyDataModel().transform(importer.to_data_model())
            if isinstance(rules, PhysicalDataModel):
                dms_rules = rules
            elif isinstance(rules, ConceptualDataModel):
                dms_rules = ConceptualToPhysical().transform(rules)
            else:
                raise ValueError(f"Unexpected rules type: {type(rules)}")

        assert not issues.has_errors, f"Import failed with issues: {issues}"

        exported = DMSExporter().export(dms_rules)

        assert len(exported.views) == 1
        first_view = next(iter(exported.views.values()))
        assert first_view.as_id() == dm.ViewId("badmodel", "GeneratingUnit", "0.1.0")
        assert "geoLocation" in first_view.properties
        prop = first_view.properties["geoLocation"]
        assert isinstance(prop, dm.MappedPropertyApply)
        # This model is missing the value type (is set #N/A in the excel file)
        assert prop.source is None
        assert prop.container == dm.ContainerId("badmodel", "GeneratingUnit")
        assert len(exported.containers) == 1
        container = next(iter(exported.containers.values()))
        assert container.as_id() == dm.ContainerId("badmodel", "GeneratingUnit")
        assert "geoLocation" in container.properties
        prop = container.properties["geoLocation"]
        assert isinstance(prop, dm.ContainerProperty)
        assert prop.type == dm.DirectRelation()
