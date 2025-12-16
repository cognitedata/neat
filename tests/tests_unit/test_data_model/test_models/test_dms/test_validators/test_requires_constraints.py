"""Tests for requires constraint validators."""

from typing import Literal, cast

import pytest

from cognite.neat._config import internal_profiles
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.validation.dms._containers import (
    MissingRequiresConstraint,
    RequiresConstraintComplicatesIngestion,
    RequiresConstraintCycle,
    UnnecessaryRequiresConstraint,
)
from cognite.neat._data_model.validation.dms._orchestrator import DmsDataModelValidation
from cognite.neat._issues import IssueList
from tests.data import SNAPSHOT_CATALOG

# Expected problems for each validator
PROBLEMS = {
    MissingRequiresConstraint: {
        # AlwaysTogetherView: AssetContainer and DescribableContainer without requires
        "AssetContainer",
        "DescribableContainer",
        # TransitiveView: ContainerA should require ContainerB (which already requires C)
        "ContainerA",
        # Partial overlap: TagContainer with TagDescribableContainer and TagAssetContainer
        "TagContainer",
    },
    UnnecessaryRequiresConstraint: {
        # OrderContainer requires CustomerContainer but they never appear together
        "OrderContainer",
        "CustomerContainer",
        "never appear together",
    },
    RequiresConstraintCycle: {
        # CycleContainerA <-> CycleContainerB cycle
        "CycleContainerA",
        "CycleContainerB",
        "cycle",
    },
    RequiresConstraintComplicatesIngestion: {
        # IngestionAssetContainer requires IngestionDescribableContainer with non-nullable property
        "IngestionAssetContainer",
        "IngestionDescribableContainer",
        "non-nullable",
    },
}


@pytest.mark.parametrize("profile", ["deep-additive", "legacy-additive"])
def test_requires_constraints_validation(
    profile: Literal["deep-additive", "legacy-additive"],
) -> None:
    """Test all requires constraint validators with the requires_constraints scenario."""
    config = internal_profiles()[profile]
    mode = config.modeling.mode
    can_run_validator = config.validation.can_run_validator

    local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
        local_scenario_name="requires_constraints",
        cdf_scenario_name="for_validators",
        modus_operandi=mode,
        include_cdm=False,
        format="snapshots",
    )
    data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

    on_success = DmsDataModelValidation(
        cdf_snapshot=cdf_snapshot,
        limits=SchemaLimits(),
        modus_operandi=mode,
        can_run_validator=can_run_validator,
    )
    on_success.run(data_model)
    by_code = cast(IssueList, on_success.issues).by_code()

    # Filter to only validators we're testing
    subset_problematic = {
        class_: PROBLEMS[class_] for class_ in PROBLEMS.keys() if can_run_validator(class_.code, class_.issue_type)
    }

    # Check that all expected validator codes are present
    expected_codes = {class_.code for class_ in subset_problematic.keys()}
    actual_codes = set(by_code.keys())
    missing_codes = expected_codes - actual_codes
    assert not missing_codes, f"Expected validator codes not found: {missing_codes}"

    # Check that all expected problems are found in the messages
    found = set()
    actual = set()
    for class_, expected_strings in subset_problematic.items():
        for expected_string in expected_strings:
            actual.add(expected_string)
            for issue in by_code.get(class_.code, []):
                if expected_string.lower() in issue.message.lower():
                    found.add(expected_string)
                    break

    missing = actual - found
    assert not missing, f"Expected problems not found in messages: {missing}"


class TestMissingRequiresConstraint:
    """More detailed tests for MissingRequiresConstraint validator."""

    def test_transitivity_avoids_redundant_recommendations(self) -> None:
        """When B requires C, recommending A requires B should be sufficient (not A requires C)."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            local_scenario_name="requires_constraints",
            cdf_scenario_name="for_validators",
            modus_operandi="additive",
            include_cdm=False,
            format="snapshots",
        )
        data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

        validation = DmsDataModelValidation(
            cdf_snapshot=cdf_snapshot,
            limits=SchemaLimits(),
            modus_operandi="additive",
        )
        validation.run(data_model)

        missing_requires_issues = [issue for issue in validation.issues if issue.code == MissingRequiresConstraint.code]
        messages = [issue.message for issue in missing_requires_issues]

        # Should recommend A requires B (which transitively covers C)
        a_requires_b = any(
            msg.startswith("Container 'my_space:ContainerA'") and "ContainerB" in msg for msg in messages
        )

        # Should NOT recommend A requires C directly (because B already requires C)
        a_requires_c_direct = any(
            msg.startswith("Container 'my_space:ContainerA'") and "always used together" in msg and "ContainerC" in msg
            for msg in messages
        )

        assert a_requires_b, f"Should recommend ContainerA requires ContainerB. Messages: {messages}"
        assert not a_requires_c_direct, (
            f"Should NOT directly recommend ContainerA requires ContainerC. Messages: {messages}"
        )

    def test_partial_overlap_recommendation(self) -> None:
        """Test that partial overlap (better coverage) recommendations are made."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            local_scenario_name="requires_constraints",
            cdf_scenario_name="for_validators",
            modus_operandi="additive",
            include_cdm=False,
            format="snapshots",
        )
        data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

        validation = DmsDataModelValidation(
            cdf_snapshot=cdf_snapshot,
            limits=SchemaLimits(),
            modus_operandi="additive",
        )
        validation.run(data_model)

        missing_requires_issues = [issue for issue in validation.issues if issue.code == MissingRequiresConstraint.code]
        messages = [issue.message for issue in missing_requires_issues]

        # Should recommend Tag requires Describable (always together)
        tag_requires_describable = any(
            "TagContainer" in msg and "always used together" in msg and "TagDescribableContainer" in msg
            for msg in messages
        )

        # Should suggest TagAssetContainer as a partial overlap option
        partial_overlap = any(
            "TagContainer" in msg and "TagAssetContainer" in msg and "improve" in msg.lower() for msg in messages
        )

        assert tag_requires_describable, (
            f"Should recommend TagContainer requires TagDescribableContainer. Messages: {messages}"
        )
        assert partial_overlap, f"Should suggest TagAssetContainer as partial overlap option. Messages: {messages}"


class TestUnnecessaryRequiresConstraint:
    """More detailed tests for UnnecessaryRequiresConstraint validator."""

    def test_detects_unnecessary_constraint(self) -> None:
        """When containers with requires constraint never appear together, flag it."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            local_scenario_name="requires_constraints",
            cdf_scenario_name="for_validators",
            modus_operandi="additive",
            include_cdm=False,
            format="snapshots",
        )
        data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

        validation = DmsDataModelValidation(
            cdf_snapshot=cdf_snapshot,
            limits=SchemaLimits(),
            modus_operandi="additive",
        )
        validation.run(data_model)

        unnecessary_issues = [issue for issue in validation.issues if issue.code == UnnecessaryRequiresConstraint.code]

        assert len(unnecessary_issues) >= 1
        assert any("OrderContainer" in issue.message for issue in unnecessary_issues)
        assert any("CustomerContainer" in issue.message for issue in unnecessary_issues)
        assert any("never appear together" in issue.message for issue in unnecessary_issues)


class TestRequiresConstraintCycle:
    """More detailed tests for RequiresConstraintCycle validator."""

    def test_detects_cycle(self) -> None:
        """Detects A -> B -> A cycle."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            local_scenario_name="requires_constraints",
            cdf_scenario_name="for_validators",
            modus_operandi="additive",
            include_cdm=False,
            format="snapshots",
        )
        data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

        validation = DmsDataModelValidation(
            cdf_snapshot=cdf_snapshot,
            limits=SchemaLimits(),
            modus_operandi="additive",
        )
        validation.run(data_model)

        cycle_issues = [issue for issue in validation.issues if issue.code == RequiresConstraintCycle.code]

        assert len(cycle_issues) >= 1
        assert any("cycle" in issue.message.lower() for issue in cycle_issues)
        assert any("CycleContainerA" in issue.message for issue in cycle_issues)
        assert any("CycleContainerB" in issue.message for issue in cycle_issues)


class TestRequiresConstraintComplicatesIngestion:
    """More detailed tests for RequiresConstraintComplicatesIngestion validator."""

    def test_detects_ingestion_complication(self) -> None:
        """When A requires B, B has non-nullable properties, and no view maps to both."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            local_scenario_name="requires_constraints",
            cdf_scenario_name="for_validators",
            modus_operandi="additive",
            include_cdm=False,
            format="snapshots",
        )
        data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

        validation = DmsDataModelValidation(
            cdf_snapshot=cdf_snapshot,
            limits=SchemaLimits(),
            modus_operandi="additive",
        )
        validation.run(data_model)

        issues = [issue for issue in validation.issues if issue.code == RequiresConstraintComplicatesIngestion.code]

        assert len(issues) >= 1
        assert any("IngestionAssetContainer" in issue.message for issue in issues)
        assert any("IngestionDescribableContainer" in issue.message for issue in issues)
        assert any("non-nullable" in issue.message.lower() for issue in issues)
