"""Tests for the autofix functionality.

End-to-end tests verifying fixes from validators resolve validation issues.
Unit tests for FixAction/FixApplicator mechanics are in test_fix.py.
"""

import pytest

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._fix import FixApplicator
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms._schema import RequestSchema
from cognite.neat._data_model.rules.dms._performance import (
    MissingRequiresConstraint,
    MissingReverseDirectRelationTargetIndex,
)
from tests.data import SNAPSHOT_CATALOG


def _snapshot_to_request_schema(snapshot: SchemaSnapshot) -> RequestSchema:
    """Convert a SchemaSnapshot to a RequestSchema for FixApplicator."""
    data_model = next(iter(snapshot.data_model.values()))
    return RequestSchema(
        dataModel=data_model,
        views=list(snapshot.views.values()),
        containers=list(snapshot.containers.values()),
        spaces=list(snapshot.spaces.values()),
        node_types=list(snapshot.node_types.keys()),
    )


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
        validator_class: type,
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

        request_schema = _snapshot_to_request_schema(local_snapshot)
        fixed_schema = FixApplicator(request_schema, fixes).apply_fixes()
        fixed_snapshot = SchemaSnapshot.from_request_schema(fixed_schema, deep_copy=False)

        # 3. Run validator again on fixed snapshot
        fixed_resources = ValidationResources(modus_operandi="additive", local=fixed_snapshot, cdf=cdf_snapshot)
        fixed_validator = validator_class(fixed_resources)
        issues_after = fixed_validator.validate()

        # 4. Verify all issues resolved
        assert len(issues_after) == 0, f"Fixes should resolve all issues, but {len(issues_after)} remain"
