from typing import Literal

import pytest

from cognite.neat._config import internal_profiles
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.rules.dms._ai_readiness import (
    DataModelMissingDescription,
    DataModelMissingName,
    EnumerationMissingDescription,
    EnumerationMissingName,
    ViewMissingDescription,
    ViewMissingName,
    ViewPropertyMissingDescription,
    ViewPropertyMissingName,
)
from cognite.neat._data_model.rules.dms._orchestrator import DmsDataModelRulesOrchestrator
from tests.data import SNAPSHOT_CATALOG

PROBLEMS = {
    DataModelMissingDescription: {"Data model is missing a description."},
    DataModelMissingName: {"Data model is missing a human-readable name."},
    ViewMissingDescription: {"CogniteDescribable", "CogniteAsset", "CogniteFile", "FileAnnotation"},
    ViewMissingName: {"CogniteDescribable", "CogniteAsset", "CogniteFile", "FileAnnotation"},
    ViewPropertyMissingDescription: {
        "name",
        "files",
        "assets",
        "equipments",
        "assetAnnotations",
        "category",
        "confidence",
    },
    ViewPropertyMissingName: {
        "name",
        "files",
        "assets",
        "equipments",
        "assetAnnotations",
        "category",
        "confidence",
    },
    EnumerationMissingName: {
        ("'blueprint' in property category of container cdf_cdm:CogniteFile is missing a human-readable name"),
        ("'document' in property category of container cdf_cdm:CogniteFile is missing a human-readable name"),
        ("'other' in property category of container cdf_cdm:CogniteFile is missing a human-readable name"),
    },
    EnumerationMissingDescription: {
        ("'blueprint' in property category of container cdf_cdm:CogniteFile is missing a human-readable description."),
        ("'document' in property category of container cdf_cdm:CogniteFile is missing a human-readable description."),
        ("'other' in property category of container cdf_cdm:CogniteFile is missing a human-readable description."),
    },
}


@pytest.mark.parametrize("profile", ["deep-additive", "legacy-additive"])
def test_validation_deep(
    profile: Literal["deep-additive", "legacy-additive"],
) -> None:
    config = internal_profiles()[profile]
    mode = config.modeling.mode
    can_run_validator = config.validation.can_run_validator

    local_snapshot, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
        "ai_readiness", "for_validators", modus_operandi=mode, include_cdm=False, format="snapshots"
    )
    data_model = SNAPSHOT_CATALOG.snapshot_to_request_schema(local_snapshot)

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
    found = set()
    actual = set()
    for class_, errors in subset_problematic.items():
        for error in errors:
            actual.add(error)
            for issue in by_code[class_.code]:
                if error in issue.message:
                    found.add(error)
                    break

    assert found == actual
