from pathlib import Path

import pytest
from cognite.client.data_classes.data_modeling import ContainerId, ViewId

from cognite.neat.v0.core._data_model.importers import ExcelImporter
from cognite.neat.v0.core._data_model.models import ConceptualDataModel, PhysicalDataModel
from cognite.neat.v0.core._data_model.models.entities._single_value import UnknownEntity
from cognite.neat.v0.core._data_model.transformers import (
    VerifyAnyDataModel,
    VerifyPhysicalDataModel,
)
from cognite.neat.v0.core._issues import IssueList, catch_issues
from cognite.neat.v0.core._issues.errors import (
    CDFMissingClientError,
    FileNotFoundNeatError,
    MetadataValueError,
    NeatValueError,
    PropertyDefinitionDuplicatedError,
    PropertyValueError,
)
from cognite.neat.v0.core._issues.warnings import (
    DeprecatedWarning,
    NotSupportedHasDataFilterLimitWarning,
    NotSupportedViewContainerLimitWarning,
    PropertyDefinitionWarning,
)
from cognite.neat.v0.core._issues.warnings._models import DanglingPropertyWarning, ViewWithoutPropertiesWarning
from tests.v0.config import DOC_RULES
from tests.v0.data import SchemaData


def invalid_rules_filepaths():
    yield pytest.param(
        DOC_RULES / "not-existing.xlsx",
        IssueList([FileNotFoundNeatError(DOC_RULES / "not-existing.xlsx")]),
        id="Not existing file",
    )

    yield pytest.param(
        SchemaData.PhysicalInvalid.invalid_metadata_xlsx,
        IssueList(
            [
                MetadataValueError(
                    field_name="externalId",
                    error=NeatValueError("value is missing."),
                ),
            ]
        ),
        id="Missing externalId in Metadata sheet.",
    )

    yield pytest.param(
        SchemaData.PhysicalInvalid.invalid_property_dms_rules_xlsx,
        IssueList(
            [
                PropertyDefinitionWarning(
                    "neat:Asset",
                    "container property",
                    "name",
                    "The type of index is not defined. Please set 'inverted:index_name' or 'btree:index_name'.",
                ),
                PropertyValueError(
                    row=5,
                    column="Max Count",
                    error=NeatValueError("Expected a float type, got 'Apple'"),
                ),
                PropertyValueError(
                    row=5,
                    column="Max Count",
                    error=NeatValueError("Expected a int type, got 'Apple'"),
                ),
            ]
        ),
        id="Invalid property specification",
    )

    yield pytest.param(
        SchemaData.PhysicalInvalid.inconsistent_container_dms_rules_xlsx,
        IssueList(
            [
                PropertyDefinitionDuplicatedError(
                    ContainerId("neat", "Flowable"),
                    "container",
                    "maxFlow",
                    frozenset({"float32", "float64"}),
                    (4, 5),
                    "rows",
                ),
                PropertyDefinitionWarning(
                    "neat:Asset",
                    "container property",
                    "name",
                    "The type of index is not defined. Please set 'inverted:index_name' or 'btree:index_name'.",
                ),
            ]
        ),
        id="Inconsistent container",
    )
    yield pytest.param(
        SchemaData.PhysicalInvalid.missing_view_container_dms_rules_xlsx,
        IssueList(
            [
                CDFMissingClientError(
                    "DataModelId(space='neat', "
                    "external_id='invalid_model', version='1') has "
                    "imported views and/or container: "
                    "{view(prefix=neat,suffix=Pump,version=1)}, "
                    "{container(prefix=neat,suffix=Pump)}."
                ),
                PropertyDefinitionWarning(
                    "neat:Asset",
                    "container property",
                    "name",
                    "The type of index is not defined. Please set 'inverted:index_name' or 'btree:index_name'.",
                ),
            ]
        ),
        id="Missing container and view definition",
    )
    yield pytest.param(
        SchemaData.PhysicalInvalid.too_many_container_per_view_xlsx,
        IssueList(
            [
                NotSupportedViewContainerLimitWarning(
                    ViewId(space="neat", external_id="Asset", version="1"),
                    11,
                ),
                NotSupportedHasDataFilterLimitWarning(
                    ViewId(space="neat", external_id="Asset", version="1"),
                    11,
                ),
            ]
        ),
        id="Too many containers per view",
    )
    yield pytest.param(
        SchemaData.PhysicalInvalid.views_without_properties_xlsx,
        IssueList(
            [
                ViewWithoutPropertiesWarning(
                    ViewId(space="neat_space", external_id="SensorWithoutProperties", version="rdf"),
                ),
            ]
        ),
        id="Views without properties",
    )


class TestExcelImporter:
    @pytest.mark.parametrize(
        "filepath, rule_type",
        [
            pytest.param(
                DOC_RULES / "cdf-dms-architect-alice.xlsx",
                PhysicalDataModel,
                id="Alice rules",
            ),
            pytest.param(
                DOC_RULES / "information-analytics-olav.xlsx",
                ConceptualDataModel,
                id="Olav user rules",
            ),
            pytest.param(
                DOC_RULES / "information-architect-david.xlsx",
                ConceptualDataModel,
                id="information-architect-david",
            ),
            pytest.param(
                DOC_RULES / "dms-analytics-olav.xlsx",
                PhysicalDataModel,
                id="dms-analytics-olav",
            ),
            pytest.param(
                DOC_RULES / "information-addition-svein-harald.xlsx",
                ConceptualDataModel,
                id="Svein Harald Enterprise Extension Information",
            ),
            pytest.param(
                DOC_RULES / "dms-addition-svein-harald.xlsx",
                PhysicalDataModel,
                id="Svein Harald Enterprise Extension DMS",
            ),
            pytest.param(
                SchemaData.Physical.pump_example_with_missing_cells_xlsx,
                PhysicalDataModel,
                id="Missing expected cell entire row drop",
            ),
        ],
    )
    def test_import_valid_rules(
        self,
        filepath: Path,
        rule_type: type[PhysicalDataModel] | type[ConceptualDataModel],
    ):
        rules = None
        with catch_issues():
            importer = ExcelImporter(filepath)
            # Cannot validate as we have no client
            rules = VerifyAnyDataModel(validate=False).transform(importer.to_data_model())

        assert isinstance(rules, rule_type)

    @pytest.mark.parametrize("filepath, expected_issues", invalid_rules_filepaths())
    def test_import_invalid_rules(self, filepath: Path, expected_issues: IssueList):
        importer = ExcelImporter(filepath)
        with catch_issues() as issues:
            read_rules = importer.to_data_model()
            _ = VerifyAnyDataModel().transform(read_rules)

        issues = sorted(issues)
        expected_issues = sorted(expected_issues)

        assert len(issues) == len(expected_issues)
        assert issues == expected_issues

    def test_import_dms_rules_missing_in_model(self):
        importer = ExcelImporter(SchemaData.Physical.missing_in_model_value_xlsx)
        rules = VerifyAnyDataModel(validate=False).transform(importer.to_data_model())

        for views in rules.views:
            assert views.in_model

    def test_import_dms_rules_with_skipped_rows_error_at_correct_loc(self):
        importer = ExcelImporter(SchemaData.Physical.pump_example_with_missing_cells_raise_issues)

        with catch_issues() as issues:
            read_rules = importer.to_data_model()
            _ = VerifyAnyDataModel().transform(read_rules)

        assert len(issues) == 1
        assert issues[0].row == 15

    def test_load_deprecated_rules(self) -> None:
        """Tests that DMS Rules with nullable and Is List columns are
        correctly translated into min and max count properties"""
        importer = ExcelImporter(SchemaData.Physical.car_dms_rules_deprecated_xlsx)
        with catch_issues() as issues:
            read_rules = importer.to_data_model()
            dms_rules = VerifyPhysicalDataModel(validate=False).transform(read_rules)

        deprecation_warning_count = sum(1 for issue in issues if isinstance(issue, DeprecatedWarning))
        assert deprecation_warning_count == 2 * len(dms_rules.properties)
        actual_properties = {
            (prop.view.external_id, prop.view_property): {
                "min_count": prop.min_count,
                "max_count": prop.max_count,
            }
            for prop in dms_rules.properties
        }
        assert actual_properties == {
            ("Car", "make"): {"min_count": None, "max_count": float("inf")},
            ("Car", "year"): {"min_count": 0, "max_count": 1},
            ("Car", "color"): {"min_count": 0, "max_count": 1},
            ("Manufacturer", "name"): {"min_count": 0, "max_count": 1},
            ("Color", "name"): {"min_count": 0, "max_count": 1},
        }

    def test_dangling_properties(self):
        """Test that dangling properties are correctly identified."""
        importer = ExcelImporter(SchemaData.Conceptual.dangling_properties_xlsx)
        with catch_issues() as issues:
            read_dm = importer.to_data_model()
            validated_dm = VerifyAnyDataModel().transform(read_dm)

        assert not issues.has_errors
        assert issues.has_warning_type(DanglingPropertyWarning)
        assert all([prop.concept == UnknownEntity() for prop in validated_dm.properties])
        assert all([prop.value_type == UnknownEntity() for prop in validated_dm.properties])
