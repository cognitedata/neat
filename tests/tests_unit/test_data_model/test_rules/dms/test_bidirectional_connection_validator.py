from typing import Literal

import pytest

from cognite.neat._config import internal_profiles
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._references import ContainerDirectReference, ContainerReference, ViewReference
from cognite.neat._data_model.models.dms._view_property import SingleReverseDirectRelationPropertyRequest
from cognite.neat._data_model.rules.dms import (
    DmsDataModelRulesOrchestrator,
    ReverseConnectionContainerMissing,
    ReverseConnectionContainerPropertyMissing,
    ReverseConnectionContainerPropertyWrongType,
    ReverseConnectionPointsToAncestor,
    ReverseConnectionSourcePropertyMissing,
    ReverseConnectionSourcePropertyWrongType,
    ReverseConnectionSourceViewMissing,
    ReverseConnectionTargetMismatch,
    ReverseConnectionTargetMissing,
)
from tests.data import SNAPSHOT_CATALOG

PROBLEMS = {
    ReverseConnectionSourceViewMissing: {"reverseUnknownToTargetViewConnection"},
    ReverseConnectionSourcePropertyMissing: {
        "reverseToDirectThatDoesNotExist",
        "reverseToViewWithoutProperties",
        "reverseThroughContainerDirectReferenceFailing",
    },
    ReverseConnectionSourcePropertyWrongType: {"reverseToEdgeConnection", "cyclicReverseA", "cyclicReverseB"},
    ReverseConnectionContainerMissing: {"reverseToDirectConnectionWithoutContainer"},
    ReverseConnectionContainerPropertyMissing: {"reverseToDirectWhichDoesHaveStorage"},
    ReverseConnectionContainerPropertyWrongType: {"reverseToAttribute"},
    ReverseConnectionTargetMissing: {"reverseToAttribute", "reverseToDirectWithoutTyping"},
    ReverseConnectionPointsToAncestor: {"innerReflection"},
    ReverseConnectionTargetMismatch: {"reverseSourceToTargetViewConnection"},
}


@pytest.mark.parametrize("profile", ["deep-additive", "legacy-additive"])
def test_validation_deep(
    profile: Literal["deep-additive", "legacy-additive"],
) -> None:
    config = internal_profiles()[profile]
    mode = config.modeling.mode
    can_run_validator = config.validation.can_run_validator

    local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
        "bi_directional_connections", "for_validators", modus_operandi=mode, include_cdm=False, format="snapshots"
    )
    data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

    data_model.containers[0].properties.pop("directWhichContainerPropertyDoesNotExistStorage")

    # simulates undefined end node type by removing the source from the property
    data_model.views[0].properties["directWithoutTyping"].source = None

    # simulates that reverse connection was configured using SDK
    data_model.views[1].properties["reverseThroughContainerDirectReferenceFailing"] = (
        SingleReverseDirectRelationPropertyRequest(
            connection_type="single_reverse_direct_relation",
            name=None,
            description=None,
            source=ViewReference(type="view", space="my_space", external_id="SourceView", version="v1"),
            through=ContainerDirectReference(
                source=ContainerReference(type="container", space="my_space", external_id="SourceContainer"),
                identifier="notImportant",
            ),
        )
    )

    config = internal_profiles()[profile]

    mode = config.modeling.mode
    can_run_validator = config.validation.can_run_validator

    # Run on success validators
    on_success = DmsDataModelRulesOrchestrator(
        cdf_snapshot=cdf_snapshot,
        limits=SchemaLimits(),
        modus_operandi=mode,
        can_run_validator=can_run_validator,
    )
    on_success.run(data_model)
    by_code = on_success.issues.by_code()

    subset_problematic = {
        class_: PROBLEMS[class_] for class_ in PROBLEMS.keys() if can_run_validator(class_.code, class_.issue_type)
    }
    assert set(class_.code for class_ in subset_problematic.keys()) - set(by_code.keys()) == set()

    # here we check that all expected problematic reversals are found
    found_problematic_reversals = set()
    actual_problematic_reversal = set()
    for class_, ill_reverse_connections in subset_problematic.items():
        for ill_reverse in ill_reverse_connections:
            actual_problematic_reversal.add(ill_reverse)
            for issue in by_code[class_.code]:
                if ill_reverse in issue.message:
                    found_problematic_reversals.add(ill_reverse)
                    break

    assert found_problematic_reversals == actual_problematic_reversal


@pytest.mark.parametrize("profile", ["deep-additive", "legacy-additive"])
def test_cyclic_reverse_relation_validator_message(
    profile: Literal["deep-additive", "legacy-additive"],
) -> None:
    config = internal_profiles()[profile]
    mode = config.modeling.mode
    can_run_validator = config.validation.can_run_validator

    local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
        "bi_directional_connections", "for_validators", modus_operandi=mode, include_cdm=False, format="snapshots"
    )
    data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

    orchestrator = DmsDataModelRulesOrchestrator(
        cdf_snapshot=cdf_snapshot,
        limits=SchemaLimits(),
        modus_operandi=mode,
        can_run_validator=can_run_validator,
    )
    orchestrator.run(data_model)
    by_code = orchestrator.issues.by_code()

    if can_run_validator(
        ReverseConnectionSourcePropertyWrongType.code, ReverseConnectionSourcePropertyWrongType.issue_type
    ):
        wrong_type_issues = by_code[ReverseConnectionSourcePropertyWrongType.code]
        cyclic_messages = [issue.message for issue in wrong_type_issues if "cyclicReverse" in issue.message]

        assert len(cyclic_messages) == 2
        for message in cyclic_messages:
            assert "reverse direct relation" in message
            assert "cycle of reverse connections" in message
            assert "cyclicReverseA" in message or "cyclicReverseB" in message


@pytest.mark.parametrize("profile", ["deep-additive", "legacy-additive"])
def test_reverse_003_fixture_variants(
    profile: Literal["deep-additive", "legacy-additive"],
) -> None:
    """Minimal fixture should surface all REVERSE-003 variants with distinct fix text."""
    config = internal_profiles()[profile]
    mode = config.modeling.mode
    can_run_validator = config.validation.can_run_validator

    local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
        "cyclic_reverse_only", "for_validators", modus_operandi=mode, include_cdm=False, format="snapshots"
    )
    data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

    orchestrator = DmsDataModelRulesOrchestrator(
        cdf_snapshot=cdf_snapshot,
        limits=SchemaLimits(),
        modus_operandi=mode,
        can_run_validator=can_run_validator,
    )
    orchestrator.run(data_model)
    by_code = orchestrator.issues.by_code()

    if not can_run_validator(
        ReverseConnectionSourcePropertyWrongType.code, ReverseConnectionSourcePropertyWrongType.issue_type
    ):
        return

    issues = by_code[ReverseConnectionSourcePropertyWrongType.code]
    assert len(issues) == 3

    edge_issue = next(i for i in issues if "reverseToEdgeConnection" in i.message)
    cyclic_issues = [i for i in issues if "cyclicReverse" in i.message]
    assert len(cyclic_issues) == 2

    assert edge_issue.fix == "Update view property to be a direct connection property"
    cyclic_fix = (
        "Update the reverse connection to point through the corresponding "
        "direct relation property on the source view (not another reverse property)."
    )
    assert all(i.fix == cyclic_fix for i in cyclic_issues)
