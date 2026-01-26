from typing import Literal

import pytest

from cognite.neat._config import internal_profiles
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._references import ContainerDirectReference, ContainerReference, ViewReference
from cognite.neat._data_model.models.dms._view_property import SingleReverseDirectRelationPropertyRequest
from cognite.neat._data_model.rules.dms import (
    DmsDataModelValidation,
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
    ReverseConnectionSourcePropertyWrongType: {"reverseToEdgeConnection"},
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
    on_success = DmsDataModelValidation(
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
