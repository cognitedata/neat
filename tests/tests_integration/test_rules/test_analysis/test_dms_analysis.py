import pytest
from cognite.client import CogniteClient

from cognite.neat.rules import importers
from cognite.neat.rules.analysis import DMSRulesAnalysis
from cognite.neat.rules.models import DMSRules
from cognite.neat.rules.models.entities import ClassEntity


@pytest.fixture(scope="module")
def core_model(cognite_client: CogniteClient) -> DMSRules:
    return importers.DMSImporter.from_data_model_id(
        cognite_client, ("sp_core_model", "core_data_model", "v1")
    ).to_rules(errors="raise")


def test_dms_analysis(core_model: DMSRules) -> None:
    analysis = DMSRulesAnalysis(core_model)

    result = analysis.classes_with_properties(consider_inheritance=True)

    assert len(result[ClassEntity(prefix="sp_core_model", suffix="Asset", version="v1")]) == 23
