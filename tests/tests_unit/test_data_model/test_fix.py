"""Tests for FixApplicator and make_auto_id."""

import pytest

from cognite.neat._data_model._fix import FixAction, FixApplicator, make_auto_id
from cognite.neat._data_model.deployer.data_classes import AddedField, ChangedField, RemovedField, SeverityType
from cognite.neat._data_model.models.dms import (
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelRequest,
    RequiresConstraintDefinition,
    SpaceRequest,
    TextProperty,
)
from cognite.neat._data_model.models.dms._indexes import BtreeIndex
from cognite.neat._data_model.models.dms._schema import RequestSchema


@pytest.fixture
def minimal_container() -> ContainerRequest:
    return ContainerRequest(
        space="test_space",
        externalId="TestContainer",
        properties={"prop1": ContainerPropertyDefinition(type=TextProperty())},
    )


@pytest.fixture
def minimal_schema(minimal_container: ContainerRequest) -> RequestSchema:
    return RequestSchema(
        dataModel=DataModelRequest(space="test_space", externalId="TestModel", version="v1", views=[]),
        containers=[minimal_container],
        spaces=[SpaceRequest(space="test_space")],
    )


class TestFixApplicatorApplyChanges:
    def test_add_constraint_to_empty_constraints(
        self, minimal_container: ContainerRequest, minimal_schema: RequestSchema
    ) -> None:
        target_ref = ContainerReference(space="other_space", external_id="OtherContainer")
        constraint = RequiresConstraintDefinition(require=target_ref)

        action = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=(
                AddedField(
                    field_path="constraints.my_constraint", new_value=constraint, item_severity=SeverityType.WARNING
                ),
            ),
            code="TEST-001",
        )
        applicator = FixApplicator(minimal_schema, [action])
        result = applicator.apply_fixes()

        fixed_container = result.containers[0]
        assert fixed_container.constraints is not None
        assert "my_constraint" in fixed_container.constraints
        assert isinstance(fixed_container.constraints["my_constraint"], RequiresConstraintDefinition)

    def test_add_index_to_empty_indexes(
        self, minimal_container: ContainerRequest, minimal_schema: RequestSchema
    ) -> None:
        index = BtreeIndex(properties=["prop1"], cursorable=True)

        action = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=(AddedField(field_path="indexes.my_index", new_value=index, item_severity=SeverityType.SAFE),),
            code="TEST-001",
        )
        applicator = FixApplicator(minimal_schema, [action])
        result = applicator.apply_fixes()

        fixed_container = result.containers[0]
        assert fixed_container.indexes is not None
        assert "my_index" in fixed_container.indexes
        assert fixed_container.indexes["my_index"].properties == ["prop1"]

    def test_change_existing_index(
        self, minimal_container: ContainerRequest, minimal_schema: RequestSchema
    ) -> None:
        old_index = BtreeIndex(properties=["prop1"], cursorable=False)
        minimal_container.indexes = {"existing_idx": old_index}

        new_index = BtreeIndex(properties=["prop1"], cursorable=True)
        action = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=(
                ChangedField(
                    field_path="indexes.existing_idx",
                    current_value=old_index,
                    new_value=new_index,
                    item_severity=SeverityType.SAFE,
                ),
            ),
            code="TEST-001",
        )
        applicator = FixApplicator(minimal_schema, [action])
        result = applicator.apply_fixes()

        updated_index = result.containers[0].indexes["existing_idx"]
        assert isinstance(updated_index, BtreeIndex)
        assert updated_index.cursorable is True

    def test_remove_constraint_cleans_up_empty_dict(
        self, minimal_container: ContainerRequest, minimal_schema: RequestSchema
    ) -> None:
        target = ContainerReference(space="target_space", external_id="TargetContainer")
        minimal_container.constraints = {"to_remove": RequiresConstraintDefinition(require=target)}

        action = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=(
                RemovedField(field_path="constraints.to_remove", current_value=None, item_severity=SeverityType.WARNING),
            ),
            code="TEST-001",
        )
        applicator = FixApplicator(minimal_schema, [action])
        result = applicator.apply_fixes()

        assert result.containers[0].constraints is None

    def test_no_fixes_returns_schema_unchanged(self, minimal_schema: RequestSchema) -> None:
        applicator = FixApplicator(minimal_schema, [])
        result = applicator.apply_fixes()

        assert result is minimal_schema


class TestFixApplicatorErrorHandling:
    def test_resource_not_found_raises(self, minimal_schema: RequestSchema) -> None:
        action = FixAction(
            resource_id=ContainerReference(space="no_space", external_id="NoContainer"),
            changes=(),
            code="TEST-001",
        )
        applicator = FixApplicator(minimal_schema, [action])

        with pytest.raises(RuntimeError, match="not found in schema"):
            applicator.apply_fixes()

    def test_invalid_field_path_raises(
        self, minimal_container: ContainerRequest, minimal_schema: RequestSchema
    ) -> None:
        action = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=(AddedField(field_path="invalid_path", new_value="value", item_severity=SeverityType.SAFE),),
            code="TEST-001",
        )
        applicator = FixApplicator(minimal_schema, [action])

        with pytest.raises(RuntimeError, match="Invalid field_path"):
            applicator.apply_fixes()

    def test_conflicting_field_paths_raises(
        self, minimal_container: ContainerRequest, minimal_schema: RequestSchema
    ) -> None:
        action_a = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=(
                AddedField(
                    field_path="constraints.same_key", new_value="value_a", item_severity=SeverityType.WARNING
                ),
            ),
            code="TEST-001",
        )
        action_b = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=(
                AddedField(
                    field_path="constraints.same_key", new_value="value_b", item_severity=SeverityType.WARNING
                ),
            ),
            code="TEST-002",
        )
        applicator = FixApplicator(minimal_schema, [action_a, action_b])

        with pytest.raises(RuntimeError, match="Conflicting fixes"):
            applicator.apply_fixes()


class TestFixApplicatorMultipleActions:
    def test_multiple_actions_on_same_resource(
        self, minimal_container: ContainerRequest, minimal_schema: RequestSchema
    ) -> None:
        target_ref = ContainerReference(space="other_space", external_id="OtherContainer")
        constraint = RequiresConstraintDefinition(require=target_ref)
        index = BtreeIndex(properties=["prop1"], cursorable=True)

        action_constraint = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=(
                AddedField(
                    field_path="constraints.my_constraint",
                    new_value=constraint,
                    item_severity=SeverityType.WARNING,
                ),
            ),
            code="TEST-001",
        )
        action_index = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=(
                AddedField(field_path="indexes.my_index", new_value=index, item_severity=SeverityType.SAFE),
            ),
            code="TEST-002",
        )
        applicator = FixApplicator(minimal_schema, [action_constraint, action_index])
        result = applicator.apply_fixes()

        fixed_container = result.containers[0]
        assert fixed_container.constraints is not None
        assert "my_constraint" in fixed_container.constraints
        assert fixed_container.indexes is not None
        assert "my_index" in fixed_container.indexes


class TestAutoGeneratedIdGeneration:
    def test_short_id_gets_suffix(self) -> None:
        result = make_auto_id("MyContainer")
        assert result == "MyContainer__auto"

    def test_long_id_is_truncated_with_hash(self) -> None:
        long_id = "VeryLongContainerOrPropertyNameThatRequiresApplyingHashing"
        result = make_auto_id(long_id)
        assert len(result) <= 43
        assert result.endswith("__auto")

    def test_deterministic(self) -> None:
        long_id = "VeryLongContainerOrPropertyNameThatRequiresApplyingHashing"
        assert make_auto_id(long_id) == make_auto_id(long_id)

    def test_different_inputs_produce_different_ids(self) -> None:
        id1 = make_auto_id("VeryLongContainerOrPropertyNameThatRequiresApplyingHashing1")
        id2 = make_auto_id("VeryLongContainerOrPropertyNameThatRequiresApplyingHashing2")
        assert id1 != id2
