"""Tests for FixApplicator and make_auto_id."""

import pytest

from cognite.neat._data_model._fix import FixAction, FixApplicator, make_auto_id
from cognite.neat._data_model.deployer.data_classes import (
    AddedField,
    ChangedField,
    FieldChange,
    RemovedField,
    SeverityType,
)
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

CONSTRAINT = RequiresConstraintDefinition(require=ContainerReference(space="other_space", external_id="OtherContainer"))
INDEX = BtreeIndex(properties=["prop1"], cursorable=True)
OLD_INDEX = BtreeIndex(properties=["prop1"], cursorable=False)
CONTAINER_REF = ContainerReference(space="test_space", external_id="TestContainer")
SAME_CHANGE = AddedField(field_path="constraints.same_key", new_value=CONSTRAINT, item_severity=SeverityType.WARNING)


def _make_container(external_id: str = "TestContainer", space: str = "test_space") -> ContainerRequest:
    return ContainerRequest(
        space=space,
        externalId=external_id,
        properties={"prop1": ContainerPropertyDefinition(type=TextProperty())},
    )


@pytest.fixture
def minimal_container() -> ContainerRequest:
    return _make_container()


@pytest.fixture
def minimal_schema(minimal_container: ContainerRequest) -> RequestSchema:
    return RequestSchema(
        dataModel=DataModelRequest(space="test_space", externalId="TestModel", version="v1", views=[]),
        containers=[minimal_container],
        spaces=[SpaceRequest(space="test_space")],
    )


class TestFixApplicatorApplyChanges:
    @pytest.mark.parametrize(
        "initial_constraints, change, expected_constraints",
        [
            pytest.param(
                None,
                AddedField(field_path="constraints.my_key", new_value=CONSTRAINT, item_severity=SeverityType.WARNING),
                {"my_key": CONSTRAINT},
                id="add_to_empty",
            ),
            pytest.param(
                {"existing": OLD_INDEX},
                ChangedField(
                    field_path="constraints.existing",
                    current_value=OLD_INDEX,
                    new_value=INDEX,
                    item_severity=SeverityType.SAFE,
                ),
                {"existing": INDEX},
                id="change_existing",
            ),
            pytest.param(
                {"to_remove": CONSTRAINT},
                RemovedField(
                    field_path="constraints.to_remove", current_value=CONSTRAINT, item_severity=SeverityType.WARNING
                ),
                None,
                id="remove_cleans_up",
            ),
        ],
    )
    def test_apply_single_change(
        self,
        minimal_container: ContainerRequest,
        minimal_schema: RequestSchema,
        initial_constraints: dict | None,
        change: FieldChange,
        expected_constraints: dict | None,
    ) -> None:
        minimal_container.constraints = initial_constraints

        action = FixAction(
            resource_id=minimal_container.as_reference(),
            changes=(change,),
            code="TEST-001",
        )
        result = FixApplicator(minimal_schema, [action]).apply_fixes()

        assert result.containers[0].constraints == expected_constraints

    def test_same_field_path_on_different_resources_does_not_conflict(self) -> None:
        container_a = _make_container("ContainerA")
        container_b = _make_container("ContainerB")
        schema = RequestSchema(
            dataModel=DataModelRequest(space="test_space", externalId="TestModel", version="v1", views=[]),
            containers=[container_a, container_b],
            spaces=[SpaceRequest(space="test_space")],
        )
        actions = [
            FixAction(resource_id=container_a.as_reference(), changes=(SAME_CHANGE,), code="TEST-001"),
            FixAction(resource_id=container_b.as_reference(), changes=(SAME_CHANGE,), code="TEST-001"),
        ]

        result = FixApplicator(schema, actions).apply_fixes()

        assert result.containers[0].constraints == {"same_key": CONSTRAINT}
        assert result.containers[1].constraints == {"same_key": CONSTRAINT}

    def test_no_fixes_returns_schema_unchanged(self, minimal_schema: RequestSchema) -> None:
        result = FixApplicator(minimal_schema, []).apply_fixes()
        assert result == minimal_schema

    @pytest.mark.parametrize(
        "actions",
        [
            pytest.param(
                [
                    FixAction(
                        resource_id=ContainerReference(space="no_space", external_id="NoContainer"),
                        changes=(),
                        code="TEST-001",
                    )
                ],
                id="resource_not_found",
            ),
            pytest.param(
                [
                    FixAction(
                        resource_id=CONTAINER_REF,
                        changes=(
                            AddedField(field_path="invalid_path", new_value="value", item_severity=SeverityType.SAFE),
                        ),
                        code="TEST-001",
                    )
                ],
                id="invalid_field_path",
            ),
            pytest.param(
                [
                    FixAction(
                        resource_id=CONTAINER_REF,
                        changes=(
                            AddedField(
                                field_path="constraints.same_key", new_value="value", item_severity=SeverityType.WARNING
                            ),
                        ),
                        code="TEST-000",
                    ),
                    FixAction(
                        resource_id=CONTAINER_REF,
                        changes=(
                            RemovedField(
                                field_path="constraints.same_key",
                                current_value="value",
                                item_severity=SeverityType.WARNING,
                            ),
                        ),
                        code="TEST-001",
                    ),
                ],
                id="conflicting_field_paths",
            ),
        ],
    )
    def test_raises_runtime_error(self, minimal_schema: RequestSchema, actions: list[FixAction]) -> None:
        with pytest.raises(RuntimeError):
            FixApplicator(minimal_schema, actions).apply_fixes()


class TestAutoGeneratedIdGeneration:
    def test_deterministic_and_valid_id_generation(self) -> None:
        ref = "VeryLongContainerOrPropertyNameThatRequiresApplyingHashing"
        assert make_auto_id(ref) == make_auto_id(ref)
        assert len(make_auto_id(ref)) <= 43

    def test_different_inputs_produce_different_ids(self) -> None:
        id1 = make_auto_id("VeryLongContainerOrPropertyNameThatRequiresApplyingHashing1")
        id2 = make_auto_id("VeryLongContainerOrPropertyNameThatRequiresApplyingHashing2")
        assert id1 != id2
