"""Tests for the autofix workflow.

End-to-end tests verifying fixes from validators resolve validation issues.
Unit tests for FixAction/FixApplicator mechanics are in test_data_model/test_fix.py.
"""

import pytest

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.rules.dms._base import DataModelRule
from cognite.neat._data_model.rules.dms._performance import (
    MissingRequiresConstraint,
    MissingReverseDirectRelationTargetIndex,
)
from cognite.neat._data_model.transformers import FixApplicator
from tests.data import SNAPSHOT_CATALOG


class TestFixWorkflow:
    """End-to-end tests verifying that applying fixes resolves validation issues."""

    @pytest.mark.parametrize(
        "scenario,cdf_scenario,include_cdm,validator_class",
        [
            pytest.param(
                "requires_constraints",
                "for_validators",
                True,
                MissingRequiresConstraint,
                id="missing_requires_constraint",
            ),
            pytest.param(
                "bi_directional_connections",
                "for_validators",
                False,
                MissingReverseDirectRelationTargetIndex,
                id="missing_index",
            ),
        ],
    )
    def test_applying_fixes_resolves_validation_issues(
        self,
        scenario: str,
        cdf_scenario: str,
        include_cdm: bool,
        validator_class: type[DataModelRule],
    ) -> None:
        """Applying fixes from a validator should resolve all validation issues it identified."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            scenario,
            cdf_scenario,
            modus_operandi="additive",
            include_cdm=include_cdm,
            format="snapshots",  # type: ignore[call-overload]
        )
        resources = ValidationResources(modus_operandi="additive", local=local_snapshot, cdf=cdf_snapshot)
        validator = validator_class(resources)

        # 1. Confirm validator finds issues
        issues_before = validator.validate()
        assert len(issues_before) > 0, "Validator should find issues for this scenario"

        # 2. Get and apply fixes via FixApplicator
        fixes = validator.fix()
        assert len(fixes) > 0, "Validator should produce fixes"

        request_schema = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)
        fixed_schema = FixApplicator(fixes).transform(request_schema)
        fixed_snapshot = SchemaSnapshot.from_request_schema(fixed_schema, deep_copy=False)

        # 3. Run validator again on fixed snapshot
        fixed_resources = ValidationResources(modus_operandi="additive", local=fixed_snapshot, cdf=cdf_snapshot)
        fixed_validator = validator_class(fixed_resources)
        issues_after = fixed_validator.validate()

        # 4. Verify all issues resolved
        assert len(issues_after) == 0, f"Fixes should resolve all issues, but {len(issues_after)} remain"
