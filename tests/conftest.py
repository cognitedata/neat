from typing import Any

import pandas as pd
import pytest

from cognite.neat.core._client.data_classes.schema import DMSSchema
from cognite.neat.core._rules.importers import ExcelImporter
from cognite.neat.core._rules.models import (
    DMSRules,
    InformationInputRules,
    InformationRules,
)
from cognite.neat.core._rules.models.dms import DMSInputRules
from cognite.neat.core._utils.spreadsheet import read_individual_sheet
from tests.config import DOC_RULES
from tests.data import SchemaData


@pytest.fixture(scope="session")
def alice_spreadsheet() -> dict[str, dict[str, Any]]:
    filepath = DOC_RULES / "cdf-dms-architect-alice.xlsx"
    excel_file = pd.ExcelFile(filepath)
    return {
        "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
        "Properties": read_individual_sheet(excel_file, "Properties", False, ["View Property"]),
        "Views": read_individual_sheet(excel_file, "Views", False, ["View"]),
        "Containers": read_individual_sheet(excel_file, "Containers", False, ["Container"]),
    }


@pytest.fixture(scope="session")
def alice_rules(alice_spreadsheet: dict[str, dict[str, Any]]) -> DMSRules:
    return DMSInputRules.load(alice_spreadsheet).as_verified_rules()


@pytest.fixture(scope="session")
def david_spreadsheet() -> dict[str, dict[str, Any]]:
    filepath = DOC_RULES / "information-architect-david.xlsx"
    excel_file = pd.ExcelFile(filepath)
    return {
        "Metadata": dict(pd.read_excel(excel_file, "Metadata", header=None).values),
        "Properties": read_individual_sheet(excel_file, "Properties", expected_headers=["Property"]),
        "Classes": read_individual_sheet(excel_file, "Classes", expected_headers=["Class"]),
    }


@pytest.fixture(scope="session")
def david_rules(david_spreadsheet: dict[str, dict[str, Any]]) -> InformationRules:
    return InformationRules.model_validate(InformationInputRules.load(david_spreadsheet).dump())


@pytest.fixture(scope="session")
def svein_harald_dms_rules() -> DMSRules:
    return ExcelImporter(DOC_RULES / "dms-addition-svein-harald.xlsx").to_rules().rules.as_verified_rules()


@pytest.fixture(scope="session")
def olav_rebuild_dms_rules() -> DMSRules:
    return ExcelImporter(DOC_RULES / "dms-rebuild-olav.xlsx").to_rules().rules.as_verified_rules()


@pytest.fixture(scope="session")
def cognite_core_schema() -> DMSSchema:
    return DMSSchema.from_zip(SchemaData.NonNeatFormats.cognite_core_v1_zip)
