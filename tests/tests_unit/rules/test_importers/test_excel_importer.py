from pathlib import Path

import pytest
from cognite.client.data_classes.data_modeling import ContainerId, ViewId
from pydantic.version import VERSION

from cognite.neat.issues import IssueList
from cognite.neat.issues.errors import (
    DuplicatedPropertyDefinitionsError,
    NeatFileNotFoundError,
    ResourceNotDefinedError,
    RowError,
)
from cognite.neat.issues.warnings import (
    HasDataFilterLimitWarning,
    ViewContainerLimitWarning,
)
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
                RowError(
                    sheet_name="Properties",
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
                DuplicatedPropertyDefinitionsError(
                    ContainerId("neat", "Flowable"),
                    "container",
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
                ResourceNotDefinedError(
                    ViewId("neat", "Pump", "1"),
                    "view",
                    location="Views Sheet",
                    column_name="View",
                    row_number=3,
                    sheet_name="Properties",
                ),
                ResourceNotDefinedError(
                    ContainerId("neat", "Pump"),
                    "container",
                    location="Containers Sheet",
                    column_name="Container",
                    row_number=3,
                    sheet_name="Properties",
                ),
            ]
        ),
        id="Missing container and view definition",
    )
    yield pytest.param(
        EXCEL_IMPORTER_DATA / "too_many_containers_per_view.xlsx",
        IssueList(
            [
                ViewContainerLimitWarning(
                    ViewId(space="neat", external_id="Asset", version="1"),
                    11,
                ),
                HasDataFilterLimitWarning(
                    ViewId(space="neat", external_id="Asset", version="1"),
                    11,
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
