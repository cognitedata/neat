from pathlib import Path

import pytest
from pydantic import ValidationError

from cognite.neat.core.configuration import Config
from cognite.neat.core.rules import to_rdf_path
from cognite.neat.core.rules.models import Property

nan = float("nan")


def generate_valid_property_test_data():
    yield pytest.param(
        {
            "Class": "GeographicalRegion",
            "Description": "nan",
            "Resource Type": "nan",
            "Property": "*",
            "Type": "nan",
            "Rule Type": "rdfpath",
            "Rule": "cim:GeographicalRegion(*)",
        },
        id="Valid rdfpath rule",
    )
    yield pytest.param(
        {
            "Class": "Terminal",
            "Description": "nan",
            "Resource Type": "nan",
            "Property": "Terminal.Substation",
            "Type": "nan",
            "Rule Type": "rawlookup",
            "Rule": "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation | "
            "TableName(Lookup, ValueColumn)",
        },
        id="Valid rawlookup rule",
    )


@pytest.mark.parametrize("raw_input", generate_valid_property_test_data())
def test_creating_valid_property(raw_input: dict):
    assert Property(**raw_input)


def generate_invalid_property_test_data():
    yield pytest.param(
        {
            "Class": "GeographicalRegion",
            "Description": "nan",
            "Resource Type": "nan",
            "Property": "*",
            "Type": "nan",
            "Rule Type": "rdfpath",
            "Rule": "GeographicalRegion(*)",
        },
        id="Invalid rdfpath rule",
    )
    yield pytest.param(
        {
            "Class": "Terminal",
            "Description": "nan",
            "Resource Type": "nan",
            "Property": "Terminal.Substation",
            "Type": "nan",
            "Rule Type": "rawlookup",
            "Rule": "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation | TableName(Lookup, )",
        },
        id="Invalid rawlookup rule",
    )


@pytest.mark.parametrize("raw_input", generate_invalid_property_test_data())
def test_creating_invalid_property(raw_input: dict):
    with pytest.raises(ValidationError):
        Property(**raw_input)


def generate_is_rdfpath_test_data():
    yield pytest.param(
        "GeographicalRegion(*)",
        False,
        id="One to many missing namespace",
    )
    yield pytest.param(
        "cim:GeographicalRegion(*)",
        True,
        id="Valid One to many",
    )
    yield pytest.param(
        "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation", True, id="Valid parent path"
    )


@pytest.mark.parametrize("raw_input, is_rdfpath_expected", generate_is_rdfpath_test_data())
def test_is_rdfpath(raw_input: str, is_rdfpath_expected: bool):
    assert to_rdf_path.is_rdfpath(raw_input) is is_rdfpath_expected


def generate_is_rawlookup_test_data():
    yield pytest.param(
        "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation | TableName(Lookup, ValueColumn)",
        True,
        id="Valid parent path with table lookup",
    )
    yield pytest.param(
        "cim:Terminal->cim:ConnectivityNode->cim:VoltageLevel->cim:Substation TableName(Lookup, ValueColumn)",
        False,
        id="Missing piping operator",
    )
    yield pytest.param(
        "cim:GeographicalRegion(*) | TableName(Lookup,)",
        False,
        id="Missing value column",
    )


@pytest.mark.parametrize("raw_input, is_rawlookup_expected", generate_is_rawlookup_test_data())
def test_is_rawlookup(raw_input: str, is_rawlookup_expected: bool):
    assert to_rdf_path.is_rawlookup(raw_input) is is_rawlookup_expected


def test_dump_and_load_default_config(tmp_path: Path):
    config = Config()
    filepath = tmp_path / "tmp_config.yaml"

    config.to_yaml(filepath)

    loaded_config = config.from_yaml(filepath)

    assert config == loaded_config
