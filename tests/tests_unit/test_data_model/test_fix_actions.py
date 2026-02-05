"""Tests for the autofix functionality.

Unit tests for FixAction mechanics and end-to-end tests verifying fixes resolve validation issues.
"""

import pytest

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model._fix_actions import FixAction
from cognite.neat._data_model._fix_helpers import make_auto_constraint_id
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.deployer.data_classes import AddedField, ChangedField, RemovedField, SeverityType
from cognite.neat._data_model.models.dms import (
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelReference,
    DataModelRequest,
    RequiresConstraintDefinition,
    SpaceReference,
    SpaceRequest,
    TextProperty,
)
from cognite.neat._data_model.models.dms._indexes import BtreeIndex
from cognite.neat._data_model.rules.dms._performance import (
    MissingRequiresConstraint,
    MissingReverseDirectRelationTargetIndex,
)
from tests.data import SNAPSHOT_CATALOG

# === Fixtures for minimal synthetic test data ===


@pytest.fixture
def minimal_container() -> ContainerRequest:
    """A minimal container for testing fix application."""
    return ContainerRequest(
        space="test_space",
        externalId="TestContainer",
        properties={"prop1": ContainerPropertyDefinition(type=TextProperty())},
    )


@pytest.fixture
def snapshot_with_container(minimal_container: ContainerRequest) -> SchemaSnapshot:
    """A snapshot containing a single container."""
    return SchemaSnapshot(
        containers={minimal_container.as_reference(): minimal_container},
        spaces={SpaceReference(space="test_space"): SpaceRequest(space="test_space")},
        data_model={
            DataModelReference(space="test_space", external_id="TestModel", version="v1"): DataModelRequest(
                space="test_space", externalId="TestModel", version="v1", views=[]
            )
        },
    )


# === Unit tests for FixAction mechanics ===


class TestFixActionApply:
    """Tests for FixAction.__call__ - the fix application mechanics."""

    def test_add_constraint_to_empty_constraints(
        self, minimal_container: ContainerRequest, snapshot_with_container: SchemaSnapshot
    ) -> None:
        """Adding a constraint when constraints is None should create the dict."""
        target_ref = ContainerReference(space="other_space", external_id="OtherContainer")
        constraint = RequiresConstraintDefinition(require=target_ref)

        fix = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=[
                AddedField(
                    field_path="constraints.my_constraint", new_value=constraint, item_severity=SeverityType.WARNING
                )
            ],
            code="TEST-001",
        )

        fix(snapshot_with_container)

        assert minimal_container.constraints is not None
        assert "my_constraint" in minimal_container.constraints
        assert minimal_container.constraints["my_constraint"].require == target_ref

    def test_add_index_to_empty_indexes(
        self, minimal_container: ContainerRequest, snapshot_with_container: SchemaSnapshot
    ) -> None:
        """Adding an index when indexes is None should create the dict."""
        index = BtreeIndex(properties=["prop1"], cursorable=True)

        fix = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=[AddedField(field_path="indexes.my_index", new_value=index, item_severity=SeverityType.SAFE)],
            code="TEST-001",
        )

        fix(snapshot_with_container)

        assert minimal_container.indexes is not None
        assert "my_index" in minimal_container.indexes
        assert minimal_container.indexes["my_index"].properties == ["prop1"]

    def test_change_existing_index_to_cursorable(
        self, minimal_container: ContainerRequest, snapshot_with_container: SchemaSnapshot
    ) -> None:
        """ChangedField should update an existing index (e.g., make it cursorable)."""
        # Setup: add initial non-cursorable index
        old_index = BtreeIndex(properties=["prop1"], cursorable=False)
        minimal_container.indexes = {"existing_idx": old_index}

        # New index with cursorable=True
        new_index = BtreeIndex(properties=["prop1"], cursorable=True)

        fix = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=[
                ChangedField(
                    field_path="indexes.existing_idx",
                    current_value=old_index,
                    new_value=new_index,
                    item_severity=SeverityType.SAFE,
                )
            ],
            code="TEST-001",
        )

        fix(snapshot_with_container)

        assert minimal_container.indexes["existing_idx"].cursorable is True

    def test_remove_constraint(
        self, minimal_container: ContainerRequest, snapshot_with_container: SchemaSnapshot
    ) -> None:
        """RemovedField should delete a constraint and clean up empty dict."""
        target = ContainerReference(space="target_space", external_id="TargetContainer")
        minimal_container.constraints = {"to_remove": RequiresConstraintDefinition(require=target)}

        fix = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=[
                RemovedField(field_path="constraints.to_remove", current_value=None, item_severity=SeverityType.WARNING)
            ],
            code="TEST-001",
        )

        fix(snapshot_with_container)

        # Empty dict should be cleaned up to None
        assert minimal_container.constraints is None

    def test_resource_not_found_raises(self, snapshot_with_container: SchemaSnapshot) -> None:
        """Applying fix to non-existent resource should raise."""
        fix = FixAction(
            resource_id=ContainerReference(space="no_space", external_id="NoContainer"),
            changes=[],
            code="TEST-001",
        )

        with pytest.raises(ValueError, match="not found"):
            fix(snapshot_with_container)

    def test_invalid_field_path_raises(
        self, minimal_container: ContainerRequest, snapshot_with_container: SchemaSnapshot
    ) -> None:
        """Field path without dot separator should raise."""
        fix = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=[AddedField(field_path="invalid_path", new_value="value", item_severity=SeverityType.SAFE)],
            code="TEST-001",
        )

        with pytest.raises(ValueError, match="Invalid field_path"):
            fix(snapshot_with_container)


# === End-to-end tests for fix workflow ===


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
            scenario, cdf_scenario, modus_operandi="additive", include_cdm=include_cdm, format="snapshots"
        )
        resources = ValidationResources(modus_operandi="additive", local=local_snapshot, cdf=cdf_snapshot)
        validator = validator_class(resources)

        # 1. Confirm validator finds issues
        issues_before = validator.validate()
        assert len(issues_before) > 0, "Validator should find issues for this scenario"

        # 2. Get and apply fixes
        fixes = validator.fix()
        assert len(fixes) > 0, "Validator should produce fixes"
        for fix in fixes:
            fix(local_snapshot)

        # 3. Run validator again on fixed snapshot
        fixed_resources = ValidationResources(modus_operandi="additive", local=local_snapshot, cdf=cdf_snapshot)
        fixed_validator = validator_class(fixed_resources)
        issues_after = fixed_validator.validate()

        # 4. Verify all issues resolved
        assert len(issues_after) == 0, f"Fixes should resolve all issues, but {len(issues_after)} remain"


# === Helper function tests ===


class TestConstraintIdGeneration:
    """Tests for make_auto_constraint_id helper."""

    def test_deterministic_and_valid_id_generation(self) -> None:
        """Same input produces same output and is within the limit."""
        ref = ContainerReference(space="s", external_id="VeryLongContainerNameThatRequiresApplyingHashing")
        assert make_auto_constraint_id(ref) == make_auto_constraint_id(ref)
        assert len(make_auto_constraint_id(ref)) <= 43

    def test_different_inputs_produce_different_ids(self) -> None:
        """Different containers produce different IDs."""
        id1 = make_auto_constraint_id(
            ContainerReference(space="s", external_id="VeryLongContainerNameThatRequiresApplyingHashing1")
        )
        id2 = make_auto_constraint_id(
            ContainerReference(space="s", external_id="VeryLongContainerNameThatRequiresApplyingHashing2")
        )
        assert id1 != id2
