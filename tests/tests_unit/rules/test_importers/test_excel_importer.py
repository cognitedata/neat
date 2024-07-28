from pathlib import Path

import pytest
from cognite.client.data_classes.data_modeling import ContainerId, ViewId
from pydantic.version import VERSION

import cognite.neat.rules.issues.spreadsheet
import cognite.neat.rules.issues.spreadsheet_file
from cognite.neat.issues import IssueList
from cognite.neat.issues.errors.external import NeatFileNotFoundError
from cognite.neat.issues.errors.resources import MultiplePropertyDefinitionsError
from cognite.neat.rules import issues as validation
from cognite.neat.rules.importers import ExcelImporter
from cognite.neat.rules.models import DMSRules, DomainRules, InformationRules, RoleTypes
from tests.config import DOC_RULES
from tests.tests_unit.rules.test_importers.constants import EXCEL_IMPORTER_DATA


def invalid_rules_filepaths():
    yield pytest.param(
        DOC_RULES / "not-existing.xlsx",
        IssueList([NeatFileNotFoundError(DOC_RULES / "not-existing.xlsx")]),
        id="Not existing file",
    )
    major, minor, *_ = VERSION.split(".")

    yield pytest.param(
        EXCEL_IMPORTER_DATA / "invalid_property_dms_rules.xlsx",
        IssueList(
            [
                validation.spreadsheet.InvalidPropertyError(
                    column="Is List",
                    row=4,
                    type="bool_parsing",
                    msg="Input should be a valid boolean, unable to interpret input",
                    input="Apple",
                    url=f"https://errors.pydantic.dev/{major}.{minor}/v/bool_parsing",
                )
            ]
        ),
        id="Invalid property specification",
    )

    yield pytest.param(
        EXCEL_IMPORTER_DATA / "inconsistent_container_dms_rules.xlsx",
        IssueList(
            [
                MultiplePropertyDefinitionsError[ContainerId](
                    ContainerId("neat", "Flowable"),
                    "Container",
                    "maxFlow",
                    frozenset({"float32", "float64"}),
                    (3, 4),
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
                cognite.neat.rules.issues.spreadsheet.NonExistingViewError(
                    column="View",
                    row=3,
                    type="value_error.missing",
                    view_id=ViewId("neat", "Pump", "1"),
                    msg="",
                    input=None,
                    url=None,
                ),
                cognite.neat.rules.issues.spreadsheet.NonExistingContainerError(
                    column="Container",
                    row=3,
                    type="value_error.missing",
                    container_id=ContainerId("neat", "Pump"),
                    msg="",
                    input=None,
                    url=None,
                ),
            ]
        ),
        id="Missing container and view definition",
    )
    yield pytest.param(
        EXCEL_IMPORTER_DATA / "too_many_containers_per_view.xlsx",
        IssueList(
            [
                cognite.neat.rules.issues.dms.ViewMapsToTooManyContainersWarning(
                    view_id=ViewId(space="neat", external_id="Asset", version="1"),
                    container_ids={
                        ContainerId(space="neat", external_id="Asset1"),
                        ContainerId(space="neat", external_id="Asset2"),
                        ContainerId(space="neat", external_id="Asset3"),
                        ContainerId(space="neat", external_id="Asset4"),
                        ContainerId(space="neat", external_id="Asset5"),
                        ContainerId(space="neat", external_id="Asset6"),
                        ContainerId(space="neat", external_id="Asset7"),
                        ContainerId(space="neat", external_id="Asset8"),
                        ContainerId(space="neat", external_id="Asset9"),
                        ContainerId(space="neat", external_id="Asset10"),
                        ContainerId(space="neat", external_id="Asset11"),
                    },
                ),
                cognite.neat.rules.issues.dms.HasDataFilterAppliedToTooManyContainersWarning(
                    view_id=ViewId(space="neat", external_id="Asset", version="1"),
                    container_ids={
                        ContainerId(space="neat", external_id="Asset1"),
                        ContainerId(space="neat", external_id="Asset2"),
                        ContainerId(space="neat", external_id="Asset3"),
                        ContainerId(space="neat", external_id="Asset4"),
                        ContainerId(space="neat", external_id="Asset5"),
                        ContainerId(space="neat", external_id="Asset6"),
                        ContainerId(space="neat", external_id="Asset7"),
                        ContainerId(space="neat", external_id="Asset8"),
                        ContainerId(space="neat", external_id="Asset9"),
                        ContainerId(space="neat", external_id="Asset10"),
                        ContainerId(space="neat", external_id="Asset11"),
                    },
                ),
            ]
        ),
        id="Too many containers per view",
    )


class TestExcelImporter:
    @pytest.mark.parametrize(
        "filepath, rule_type, convert_to",
        [
            pytest.param(DOC_RULES / "cdf-dms-architect-alice.xlsx", DMSRules, RoleTypes.information, id="Alice rules"),
            pytest.param(
                DOC_RULES / "information-analytics-olav.xlsx",
                InformationRules,
                RoleTypes.dms,
                id="Olav user rules",
            ),
            pytest.param(DOC_RULES / "expert-wind-energy-jon.xlsx", DomainRules, None, id="expert-wind-energy-jon"),
            pytest.param(DOC_RULES / "expert-grid-emma.xlsx", DomainRules, None, id="expert-grid-emma"),
            pytest.param(
                DOC_RULES / "information-architect-david.xlsx",
                InformationRules,
                RoleTypes.dms,
                id="information-architect-david",
            ),
            pytest.param(
                DOC_RULES / "dms-analytics-olav.xlsx",
                DMSRules,
                RoleTypes.information,
                id="dms-analytics-olav",
            ),
            pytest.param(
                DOC_RULES / "information-addition-svein-harald.xlsx",
                InformationRules,
                RoleTypes.dms,
                id="Svein Harald Enterprise Extension Information",
            ),
            pytest.param(
                DOC_RULES / "dms-addition-svein-harald.xlsx",
                DMSRules,
                RoleTypes.information,
                id="Svein Harald Enterprise Extension DMS",
            ),
        ],
    )
    def test_import_valid_rules(
        self,
        filepath: Path,
        rule_type: type[DMSRules] | type[InformationRules] | type[DomainRules],
        convert_to: RoleTypes | None,
    ):
        importer = ExcelImporter(filepath)
        rules = importer.to_rules(errors="raise")
        assert isinstance(rules, rule_type)
        if convert_to is not None:
            converted = importer._to_output(rules, IssueList(), errors="raise", role=convert_to)
            assert converted.metadata.role is convert_to

    @pytest.mark.parametrize("filepath, expected_issues", invalid_rules_filepaths())
    def test_import_invalid_rules(self, filepath: Path, expected_issues: IssueList):
        importer = ExcelImporter(filepath)

        _, issues = importer.to_rules(errors="continue")

        issues = sorted(issues)
        expected_issues = sorted(expected_issues)

        assert len(issues) == len(expected_issues)
        assert issues == expected_issues
