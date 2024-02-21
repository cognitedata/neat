from typing import Any

import pandas as pd
import pytest

from cognite.neat.rules.models._rules.dms_architect_rules import (
    DMSRules,
)
from tests.config import DOC_KNOWLEDGE_ACQUISITION_TUTORIAL
from tests.tests_unit.rules.test_models.utils import _read_spreadsheet


@pytest.fixture(scope="session")
def alice_spreadsheet() -> dict[str, dict[str, Any]]:
    filepath = DOC_KNOWLEDGE_ACQUISITION_TUTORIAL / "cdf-dms-architect-alice.xlsx"
    excel_file = pd.ExcelFile(filepath)
    return {
        "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
        "Properties": _read_spreadsheet(excel_file, "Properties", skiprows=1),
        "Views": _read_spreadsheet(excel_file, "Views", skiprows=1),
        "Containers": _read_spreadsheet(excel_file, "Containers", skiprows=1),
    }


@pytest.fixture(scope="session")
def alice_rules(alice_spreadsheet: dict[str, dict[str, Any]]) -> DMSRules:
    return DMSRules.model_validate(alice_spreadsheet)
