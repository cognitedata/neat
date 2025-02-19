from pathlib import Path

import pytest
from cognite.client.data_classes.data_modeling import ContainerId, ViewId

from cognite.neat._issues import IssueList, catch_issues
from cognite.neat._issues.errors import (
    CDFMissingClientError,
    FileNotFoundNeatError,
    MetadataValueError,
    NeatValueError,
    PropertyDefinitionDuplicatedError,
    PropertyValueError,
)
from cognite.neat._issues.warnings import (
    NotSupportedHasDataFilterLimitWarning,
    NotSupportedViewContainerLimitWarning,
)
from cognite.neat._rules.importers import ExcelImporter
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.transformers import VerifyAnyRules
from tests.config import DATA_FOLDER, DOC_RULES
from tests.tests_unit.rules.test_importers.constants import EXCEL_IMPORTER_DATA


def invalid_rules_filepaths():
    yield pytest.param(
        DOC_RULES / "not-existing.xlsx",
        IssueList([FileNotFoundNeatError(DOC_RULES / "not-existing.xlsx")]),
        id="Not existing file",
    )

    yield pytest.param(
        EXCEL_IMPORTER_DATA / "invalid_metadata.xlsx",
        IssueList(
            [
                MetadataValueError(
                    field_name="space",
                    error=NeatValueError("value is missing."),
                ),
            ]
        ),
        id="Missing space in Metadata sheet.",
    )

    yield pytest.param(
        EXCEL_IMPORTER_DATA / "invalid_property_dms_rules.xlsx",
        IssueList(
            [
                PropertyValueError(
                    row=5,
                    column="Is List",
                    error=NeatValueError("Expected a bool type, got 'Apple'"),
                ),
            ]
        ),
        id="Invalid property specification",
    )

    yield pytest.param(
        EXCEL_IMPORTER_DATA / "inconsistent_container_dms_rules.xlsx",
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
            ]
        ),
        id="Inconsistent container",
    )
    yield pytest.param(
        EXCEL_IMPORTER_DATA / "missing_view_container_dms_rules.xlsx",
        IssueList(
            [
                CDFMissingClientError(
                    "DataModelId(space='neat', "
                    "external_id='invalid_model', version='1') has "
                    "imported views and/or container: "
                    "{view(prefix=neat,suffix=Pump,version=1)}, "
                    "{container(prefix=neat,suffix=Pump)}."
                ),
            ]
        ),
        id="Missing container and view definition",
    )
    yield pytest.param(
        EXCEL_IMPORTER_DATA / "too_many_containers_per_view.xlsx",
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


class TestExcelImporter:
    @pytest.mark.parametrize(
        "filepath, rule_type",
        [
            pytest.param(
                DOC_RULES / "cdf-dms-architect-alice.xlsx",
                DMSRules,
                id="Alice rules",
            ),
            pytest.param(
                DOC_RULES / "information-analytics-olav.xlsx",
                InformationRules,
                id="Olav user rules",
            ),
            pytest.param(
                DOC_RULES / "information-architect-david.xlsx",
                InformationRules,
                id="information-architect-david",
            ),
            pytest.param(
                DOC_RULES / "dms-analytics-olav.xlsx",
                DMSRules,
                id="dms-analytics-olav",
            ),
            pytest.param(
                DOC_RULES / "information-addition-svein-harald.xlsx",
                InformationRules,
                id="Svein Harald Enterprise Extension Information",
            ),
            pytest.param(
                DOC_RULES / "dms-addition-svein-harald.xlsx",
                DMSRules,
                id="Svein Harald Enterprise Extension DMS",
            ),
            pytest.param(
                DATA_FOLDER / "pump_example_with_missing_cells.xlsx",
                DMSRules,
                id="Missing expected cell entire row drop",
            ),
        ],
    )
    def test_import_valid_rules(
        self,
        filepath: Path,
        rule_type: type[DMSRules] | type[InformationRules],
    ):
        rules = None
        with catch_issues():
            importer = ExcelImporter(filepath)
            # Cannot validate as we have no client
            rules = VerifyAnyRules(validate=False).transform(importer.to_rules())

        assert isinstance(rules, rule_type)

    @pytest.mark.parametrize("filepath, expected_issues", invalid_rules_filepaths())
    def test_import_invalid_rules(self, filepath: Path, expected_issues: IssueList):
        importer = ExcelImporter(filepath)
        with catch_issues() as issues:
            read_rules = importer.to_rules()
            _ = VerifyAnyRules().transform(read_rules)

        issues = sorted(issues)
        expected_issues = sorted(expected_issues)

        assert len(issues) == len(expected_issues)
        assert issues == expected_issues

    def test_import_dms_rules_missing_in_model(self):
        importer = ExcelImporter(DATA_FOLDER / "missing-in-model-value.xlsx")
        rules = VerifyAnyRules(validate=False).transform(importer.to_rules())

        for views in rules.views:
            assert views.in_model

    def test_import_dms_rules_with_skipped_rows_error_at_correct_loc(self):
        importer = ExcelImporter(DATA_FOLDER / "pump_example_with_missing_cells_raise_issues.xlsx")

        with catch_issues() as issues:
            read_rules = importer.to_rules()
            _ = VerifyAnyRules().transform(read_rules)

        assert len(issues) == 1
        assert issues[0].row == 15
