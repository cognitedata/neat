"""Tests for the fix action functionality in validators."""

import pytest

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._fix_actions import FixAction
from cognite.neat._data_model._fix_helpers import (
    AUTO_SUFFIX,
    HASH_LENGTH,
    MAX_BASE_LENGTH_NO_HASH,
    MAX_IDENTIFIER_LENGTH,
    make_auto_constraint_id,
)
from cognite.neat._data_model.deployer.data_classes import AddedField, SeverityType
from cognite.neat._data_model.models.dms._constraints import RequiresConstraintDefinition
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._references import ContainerReference
from cognite.neat._data_model.rules.dms._orchestrator import DmsDataModelFixer
from cognite.neat._data_model.rules.dms._performance import MissingRequiresConstraint
from tests.data import SNAPSHOT_CATALOG


class TestFixAction:
    """Tests for the FixAction class."""

    def test_fix_action_equality(self) -> None:
        """Test that FixAction equality is based on resource_id and changes."""
        source = ContainerReference(space="test", external_id="SourceContainer")
        dest = ContainerReference(space="test", external_id="DestContainer")
        other_dest = ContainerReference(space="test", external_id="OtherContainer")

        action1 = FixAction(
            code="TEST-001",
            resource_id=source,
            new_value=None,
            changes=[
                AddedField(
                    field_path="constraints.dest__auto",
                    new_value=RequiresConstraintDefinition(require=dest),
                    item_severity=SeverityType.WARNING,
                )
            ],
            message="Test action 1",
        )
        action2 = FixAction(
            code="TEST-001",
            resource_id=source,
            new_value=None,
            changes=[
                AddedField(
                    field_path="constraints.dest__auto",
                    new_value=RequiresConstraintDefinition(require=dest),
                    item_severity=SeverityType.WARNING,
                )
            ],
            message="Different message",
        )
        action3 = FixAction(
            code="TEST-001",
            resource_id=source,
            new_value=None,
            changes=[
                AddedField(
                    field_path="constraints.other__auto",
                    new_value=RequiresConstraintDefinition(require=other_dest),
                    item_severity=SeverityType.WARNING,
                )
            ],
        )

        assert action1 == action2  # Same resource_id and changes
        assert action1 != action3  # Different changes

    def test_fix_action_hash(self) -> None:
        """Test that FixAction can be used in sets/dicts."""
        source = ContainerReference(space="test", external_id="SourceContainer")
        dest = ContainerReference(space="test", external_id="DestContainer")

        action1 = FixAction(
            code="TEST-001",
            resource_id=source,
            new_value=None,
            changes=[
                AddedField(
                    field_path="constraints.dest__auto",
                    new_value=RequiresConstraintDefinition(require=dest),
                    item_severity=SeverityType.WARNING,
                )
            ],
        )
        action2 = FixAction(
            code="TEST-001",
            resource_id=source,
            new_value=None,
            changes=[
                AddedField(
                    field_path="constraints.dest__auto",
                    new_value=RequiresConstraintDefinition(require=dest),
                    item_severity=SeverityType.WARNING,
                )
            ],
            message="Different message",
        )

        # Same resource_id and changes should have same hash
        assert hash(action1) == hash(action2)

        # Can be used in sets
        actions_set = {action1, action2}
        assert len(actions_set) == 1

    def test_fix_id_property(self) -> None:
        """Test that fix_id is generated from code, resource_id and field paths."""
        source = ContainerReference(space="test", external_id="SourceContainer")
        dest = ContainerReference(space="test", external_id="DestContainer")

        action = FixAction(
            code="TEST-001",
            resource_id=source,
            new_value=None,
            changes=[
                AddedField(
                    field_path="constraints.dest__auto",
                    new_value=RequiresConstraintDefinition(require=dest),
                    item_severity=SeverityType.WARNING,
                )
            ],
        )

        # fix_id should contain code, resource_id, and field path
        assert "TEST-001" in action.fix_id
        assert "constraints.dest__auto" in action.fix_id


class TestMissingRequiresConstraintFix:
    """Tests for MissingRequiresConstraint validator fix() method."""

    def test_fix_returns_fix_actions_for_missing_constraints(self) -> None:
        """Test that the fix() method returns FixAction objects."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            "requires_constraints",
            "for_validators",
            modus_operandi="additive",
            include_cdm=True,
            format="snapshots",
        )

        validation_resources = ValidationResources(
            modus_operandi="additive",
            local=local_snapshot,
            cdf=cdf_snapshot,
        )

        validator = MissingRequiresConstraint(validation_resources)
        fix_actions = validator.fix()

        # Should have at least one fix action
        assert len(fix_actions) > 0

        # Each fix action should have proper structure
        for action in fix_actions:
            assert action.fix_id.startswith(MissingRequiresConstraint.code)
            assert action.code == MissingRequiresConstraint.code
            assert callable(action)  # Action itself is callable

    def test_fix_actions_have_constraint_changes(self) -> None:
        """Test that fix actions have AddedField changes for constraints."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            "requires_constraints",
            "for_validators",
            modus_operandi="additive",
            include_cdm=True,
            format="snapshots",
        )

        validation_resources = ValidationResources(
            modus_operandi="additive",
            local=local_snapshot,
            cdf=cdf_snapshot,
        )

        validator = MissingRequiresConstraint(validation_resources)
        fix_actions = validator.fix()

        # Each fix action should have AddedField changes for constraints
        for action in fix_actions:
            assert len(action.changes) > 0
            for change in action.changes:
                assert isinstance(change, AddedField)
                assert change.field_path.startswith("constraints.")
                assert change.field_path.endswith("__auto")
                assert isinstance(change.new_value, RequiresConstraintDefinition)

    def test_validate_and_fix_are_independent(self) -> None:
        """Test that validate() returns issues and fix() returns fix actions separately."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            "requires_constraints",
            "for_validators",
            modus_operandi="additive",
            include_cdm=True,
            format="snapshots",
        )

        validation_resources = ValidationResources(
            modus_operandi="additive",
            local=local_snapshot,
            cdf=cdf_snapshot,
        )

        validator = MissingRequiresConstraint(validation_resources)

        # validate() should return Recommendation objects
        issues = validator.validate()
        assert all(hasattr(issue, "message") for issue in issues)

        # fix() should return FixAction objects
        fix_actions = validator.fix()
        assert all(isinstance(action, FixAction) for action in fix_actions)


class TestDmsDataModelFixer:
    """Tests for the DmsDataModelFixer orchestrator."""

    def test_fixer_applies_missing_constraint_fixes(self) -> None:
        """Test that the fixer adds missing requires constraints."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            "requires_constraints",
            "for_validators",
            modus_operandi="additive",
            include_cdm=True,
            format="snapshots",
        )
        data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

        # Verify validator has fixes available
        validation_resources = ValidationResources(
            modus_operandi="additive",
            local=local_snapshot,
            cdf=cdf_snapshot,
        )
        validator = MissingRequiresConstraint(validation_resources)
        available_fixes = validator.fix()

        if not available_fixes:
            pytest.skip("No fixes available in test data")

        # Run the fixer
        fixer = DmsDataModelFixer(
            cdf_snapshot=cdf_snapshot,
            limits=SchemaLimits(),
            modus_operandi="additive",
            enable_alpha_validators=True,
            apply_fixes=True,
        )
        fixer.run(data_model)

        # Check that fixes were applied
        assert len(fixer.applied_fixes) > 0

        # Verify at least one constraint with __auto suffix was added
        auto_constraints_found = False
        for container in data_model.containers:
            if container.constraints:
                for constraint_id in container.constraints:
                    if constraint_id.endswith("__auto"):
                        auto_constraints_found = True
                        break
        assert auto_constraints_found, "Expected at least one __auto constraint to be added"

    def test_fixer_without_apply_does_not_modify(self) -> None:
        """Test that fixer with apply_fixes=False doesn't modify the schema."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            "requires_constraints",
            "for_validators",
            modus_operandi="additive",
            include_cdm=True,
            format="snapshots",
        )
        data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

        # Take a snapshot of container constraints before
        constraints_before = {
            c.as_reference(): dict(c.constraints) if c.constraints else {} for c in data_model.containers
        }

        # Run fixer without applying
        fixer = DmsDataModelFixer(
            cdf_snapshot=cdf_snapshot,
            limits=SchemaLimits(),
            modus_operandi="additive",
            enable_alpha_validators=True,
            apply_fixes=False,
        )
        fixer.run(data_model)

        # Check that no fixes were applied
        assert len(fixer.applied_fixes) == 0

        # Verify schema wasn't modified
        constraints_after = {
            c.as_reference(): dict(c.constraints) if c.constraints else {} for c in data_model.containers
        }
        assert constraints_before == constraints_after

    def test_fixer_orders_fixes_by_fix_id(self) -> None:
        """Test that fixes are applied in a deterministic order (by fix_id)."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            "requires_constraints",
            "for_validators",
            modus_operandi="additive",
            include_cdm=True,
            format="snapshots",
        )
        data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

        fixer = DmsDataModelFixer(
            cdf_snapshot=cdf_snapshot,
            limits=SchemaLimits(),
            modus_operandi="additive",
            enable_alpha_validators=True,
            apply_fixes=True,
        )
        fixer.run(data_model)

        # Check that applied fixes are in fix_id order
        if len(fixer.applied_fixes) > 1:
            for i in range(len(fixer.applied_fixes) - 1):
                assert fixer.applied_fixes[i].fix_id <= fixer.applied_fixes[i + 1].fix_id


class TestAppliedFixesTracking:
    """Tests for tracking which fixes were applied by the fixer."""

    def test_fixer_tracks_applied_fixes(self) -> None:
        """Test that the fixer correctly tracks applied fix actions."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            "requires_constraints",
            "for_validators",
            modus_operandi="additive",
            include_cdm=True,
            format="snapshots",
        )
        data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

        # Run the fixer with fixes applied
        fixer = DmsDataModelFixer(
            cdf_snapshot=cdf_snapshot,
            limits=SchemaLimits(),
            modus_operandi="additive",
            enable_alpha_validators=True,
            apply_fixes=True,
        )
        fixer.run(data_model)

        # If any fixes were applied, check their structure
        if len(fixer.applied_fixes) > 0:
            # Each applied fix should be a FixAction with proper structure
            for fix_action in fixer.applied_fixes:
                assert isinstance(fix_action, FixAction)
                assert fix_action.message  # Specific action description
                assert fix_action.fix_id

    def test_fixer_no_applied_fixes_when_not_applying(self) -> None:
        """Test that applied_fixes is empty when apply_fixes is False."""
        local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
            "requires_constraints",
            "for_validators",
            modus_operandi="additive",
            include_cdm=True,
            format="snapshots",
        )
        data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

        # Run fixer without applying
        fixer = DmsDataModelFixer(
            cdf_snapshot=cdf_snapshot,
            limits=SchemaLimits(),
            modus_operandi="additive",
            enable_alpha_validators=True,
            apply_fixes=False,
        )
        fixer.run(data_model)

        # No fixes applied
        assert len(fixer.applied_fixes) == 0


class TestConstraintIdGeneration:
    """Tests for constraint ID generation."""

    def test_auto_constraint_id_within_limit(self) -> None:
        """Test that generated constraint IDs are within the 43-character limit."""
        # Short external_id should work normally
        short_ref = ContainerReference(space="test", external_id="ShortName")
        constraint_id = make_auto_constraint_id(short_ref)
        assert constraint_id == "ShortName__auto"
        assert len(constraint_id) <= MAX_IDENTIFIER_LENGTH

    def test_auto_constraint_id_truncates_long_names_with_hash(self) -> None:
        """Test that long external_ids are truncated with hash to ensure uniqueness."""
        # External ID that's too long (50 characters)
        long_name = "A" * 50
        long_ref = ContainerReference(space="test", external_id=long_name)
        constraint_id = make_auto_constraint_id(long_ref)

        # Should be exactly at the limit
        assert len(constraint_id) == MAX_IDENTIFIER_LENGTH
        assert constraint_id.endswith(AUTO_SUFFIX)
        # Should contain underscore before hash
        assert "_" in constraint_id
        # Hash should be included (8 hex characters before __auto)
        parts = constraint_id.replace(AUTO_SUFFIX, "").rsplit("_", 1)
        assert len(parts) == 2
        assert len(parts[1]) == HASH_LENGTH

    def test_auto_constraint_id_hash_ensures_uniqueness(self) -> None:
        """Test that different long names with same prefix get different hashes."""
        # Two containers with same first 28 chars but different endings
        prefix = "A" * 28
        ref1 = ContainerReference(space="test", external_id=prefix + "XXXXXXXXXXXXXXX")
        ref2 = ContainerReference(space="test", external_id=prefix + "YYYYYYYYYYYYYYY")

        constraint_id1 = make_auto_constraint_id(ref1)
        constraint_id2 = make_auto_constraint_id(ref2)

        # Should be different due to different hashes
        assert constraint_id1 != constraint_id2

    def test_auto_constraint_id_exactly_at_limit_no_hash(self) -> None:
        """Test external_id that's exactly at the max base length (37 chars) needs no hash."""
        # External ID exactly at MAX_BASE_LENGTH_NO_HASH (37 characters)
        exact_name = "B" * MAX_BASE_LENGTH_NO_HASH
        exact_ref = ContainerReference(space="test", external_id=exact_name)
        constraint_id = make_auto_constraint_id(exact_ref)

        assert len(constraint_id) == MAX_IDENTIFIER_LENGTH
        assert constraint_id == exact_name + AUTO_SUFFIX

    def test_auto_constraint_id_one_over_limit_uses_hash(self) -> None:
        """Test external_id that's 1 char over the limit uses hash."""
        # External ID 1 character over the limit
        over_name = "C" * (MAX_BASE_LENGTH_NO_HASH + 1)
        over_ref = ContainerReference(space="test", external_id=over_name)
        constraint_id = make_auto_constraint_id(over_ref)

        assert len(constraint_id) == MAX_IDENTIFIER_LENGTH
        assert constraint_id.endswith(AUTO_SUFFIX)
        # Should have hash
        parts = constraint_id.replace(AUTO_SUFFIX, "").rsplit("_", 1)
        assert len(parts) == 2
        assert len(parts[1]) == HASH_LENGTH
