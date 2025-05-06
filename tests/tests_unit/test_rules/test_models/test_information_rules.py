from datetime import datetime
from typing import Any

import pytest

from cognite.neat.core._constants import DMS_CONTAINER_PROPERTY_SIZE_LIMIT
from cognite.neat.core._issues import NeatError
from cognite.neat.core._issues._base import MultiValueError
from cognite.neat.core._issues.errors import ResourceNotDefinedError
from cognite.neat.core._issues.errors._resources import ResourceDuplicatedError
from cognite.neat.core._rules._shared import ReadRules
from cognite.neat.core._rules.models import DMSRules, data_types
from cognite.neat.core._rules.models.data_types import DataType, String
from cognite.neat.core._rules.models.entities import ClassEntity, MultiValueTypeInfo
from cognite.neat.core._rules.models.information import (
    InformationClass,
    InformationInputRules,
    InformationProperty,
    InformationRules,
    InformationValidation,
)
from cognite.neat.core._rules.models.information._rules_input import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
)
from cognite.neat.core._rules.transformers._converters import (
    InformationToDMS,
    ToCompliantEntities,
    _InformationRulesConverter,
)
from cognite.neat.core._rules.transformers._verification import VerifyAnyRules


def case_insensitive_value_types():
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
                "schema": "complete",
                "creator": "Jon, Emma, David",
                "space": "power",
                "external_id": "power2consumer",
                "created": datetime(2024, 2, 9, 0, 0),
                "updated": datetime(2024, 2, 9, 0, 0),
                "version": "0.1.0",
                "name": "Power to Consumer Data Model",
            },
            "Classes": [
                {
                    "Class": "GeneratingUnit",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#GeneratingUnit",
                    "Match": "exact",
                }
            ],
            "Properties": [
                {
                    "Class": "GeneratingUnit",
                    "Property": "name",
                    "Description": None,
                    "Value Type": "StrING",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Transformation": None,
                }
            ],
        },
        String(),
        id="case_insensitive",
    )


def duplicated_entries():
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
                "schema": "complete",
                "creator": "Jon, Emma, David",
                "space": "power",
                "external_id": "power2consumer",
                "created": datetime(2024, 2, 9, 0, 0),
                "updated": datetime(2024, 2, 9, 0, 0),
                "version": "0.1.0",
                "name": "Power to Consumer Data Model",
            },
            "Classes": [
                {
                    "Class": "GeneratingUnit",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#GeneratingUnit",
                    "Match": "exact",
                },
                {
                    "Class": "GeneratingUnit",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#GeneratingUnit",
                    "Match": "exact",
                },
            ],
            "Properties": [
                {
                    "Class": "GeneratingUnit",
                    "Property": "name",
                    "Description": None,
                    "Value Type": "StrING",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Transformation": None,
                },
                {
                    "Class": "GeneratingUnit",
                    "Property": "name",
                    "Description": None,
                    "Value Type": "StrING",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Transformation": None,
                },
            ],
        },
        {
            ResourceDuplicatedError(
                identifier="name",
                resource_type="property",
                location="the Properties sheet at row 1 and 2 if data model is read from a spreadsheet.",
            ),
            ResourceDuplicatedError(
                identifier=ClassEntity(prefix="power", suffix="GeneratingUnit"),
                resource_type="class",
                location="the Classes sheet at row 1 and 2 if data model is read from a spreadsheet.",
            ),
        },
        id="duplicated_entries",
    )


def incomplete_rules_case():
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
                "schema": "complete",
                "creator": "Jon, Emma, David",
                "space": "power",
                "external_id": "power2consumer",
                "created": datetime(2024, 2, 9, 0, 0),
                "updated": datetime(2024, 2, 9, 0, 0),
                "version": "0.1.0",
                "name": "Power to Consumer Data Model",
            },
            "Classes": [
                {
                    "Class": "GeneratingUnit",
                    "Description": None,
                    "Implements": None,
                }
            ],
            "Properties": [
                {
                    "Class": "GeneratingUnit2",
                    "Property": "name",
                    "Description": None,
                    "Value Type": "string",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Transformation": "cim:GeneratingUnit",
                }
            ],
        },
        [
            ResourceNotDefinedError[ClassEntity](
                ClassEntity(prefix="power", suffix="GeneratingUnit2"),
                "class",
                "Classes sheet",
            ),
            ResourceNotDefinedError[ClassEntity](
                ClassEntity(prefix="power", suffix="GeneratingUnit"),
                "class",
                "Classes sheet",
            ),
        ],
        id="missing_rule",
    )


class TestInformationRules:
    @pytest.mark.parametrize("duplicated_rules, expected_exception", list(duplicated_entries()))
    def test_duplicated_entries(self, duplicated_rules, expected_exception) -> None:
        input_rules = ReadRules(rules=InformationInputRules.load(duplicated_rules), read_context={})
        transformer = VerifyAnyRules(validate=True)

        with pytest.raises(MultiValueError) as e:
            _ = transformer.transform(input_rules)

        assert set(e.value.errors) == expected_exception

    def test_load_valid_jon_rules(self, david_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = InformationRules.model_validate(InformationInputRules.load(david_spreadsheet).dump())

        assert isinstance(valid_rules, InformationRules)

        sample_expected_properties = {
            "power:WindTurbine.manufacturer",
            "power:Substation.secondaryPowerLine",
            "power:WindFarm.exportCable",
        }
        missing = sample_expected_properties - {f"{prop.class_}.{prop.property_}" for prop in valid_rules.properties}
        assert not missing, f"Missing properties: {missing}"

    @pytest.mark.parametrize("incomplete_rules, expected_exception", list(incomplete_rules_case()))
    @pytest.mark.skip("Temp skipping: enabling in new PR")
    def test_incomplete_rules(self, incomplete_rules: dict[str, dict[str, Any]], expected_exception: NeatError) -> None:
        rules = InformationRules.model_validate(InformationInputRules.load(incomplete_rules).dump())
        issues = InformationValidation(rules).validate()

        assert len(issues) == 2
        assert set(issues) == set(expected_exception)

    @pytest.mark.parametrize("rules, expected_exception", list(case_insensitive_value_types()))
    def test_case_insensitivity(self, rules: dict[str, dict[str, Any]], expected_exception: DataType) -> None:
        assert InformationRules.model_validate(rules).properties[0].value_type == expected_exception

    def test_david_as_dms(self, david_spreadsheet: dict[str, dict[str, Any]]) -> None:
        info_rules = InformationRules.model_validate(david_spreadsheet)

        dms_rules = InformationToDMS().transform(info_rules)

        assert isinstance(dms_rules, DMSRules)

        # making sure linking is done on metadata level
        assert dms_rules.metadata.logical == info_rules.metadata.identifier

        info_props = {prop.neatId: prop for prop in info_rules.properties}
        dms_props = {prop.neatId: prop for prop in dms_rules.properties}

        for dms_id in dms_props.keys():
            assert info_props[dms_props[dms_id].logical].physical == dms_id

        for info_id in info_props.keys():
            assert dms_props[info_props[info_id].physical].logical == info_id


class TestInformationRulesConverter:
    @pytest.mark.parametrize(
        "prefix, expected_space",
        [
            pytest.param("neat", "neat", id="No substitutions"),
            pytest.param("my space", "my_space", id="Space with space character"),
            pytest.param("1my-space", "a1my-space", id="Space starting with number"),
            pytest.param("m" * 69, "m" * 43, id="Space with more than 43 characters"),
            pytest.param("my_space_", "my_space1", id="Space ending with underscore"),
        ],
    )
    def test_to_space(self, prefix: str, expected_space: str) -> None:
        actual_space = _InformationRulesConverter._to_space(prefix)

        assert actual_space == expected_space

    def test_convert_above_container_limit(self) -> None:
        info = InformationInputRules(
            metadata=InformationInputMetadata(
                space="bad_model",
                external_id="bad_model",
                name="Bad Model",
                version="0.1.0",
                creator="Anders",
            ),
            classes=[InformationInputClass(class_="MassiveClass")],
            properties=[
                InformationInputProperty(
                    class_="MassiveClass",
                    property_=f"property_{no}",
                    value_type="string",
                    max_count=1,
                )
                for no in range(DMS_CONTAINER_PROPERTY_SIZE_LIMIT + 1)
            ],
        ).as_verified_rules()

        dms_rules = InformationToDMS().transform(info)

        assert len(dms_rules.containers) == 2


def non_compliant_entities():
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
                "schema": "complete",
                "creator": "Jon, Emma, David",
                "namespace": "http://purl.org/cognite/power2consumer",
                "space": "power_or_not",
                "external_id": "powerfulModel",
                "created": datetime(2024, 2, 9, 0, 0),
                "updated": datetime(2024, 2, 9, 0, 0),
                "version": "0.1.0",
                "title": "Power to Consumer Data Model",
                "license": "CC-BY 4.0",
                "rights": "Free for use",
            },
            "Classes": [
                {
                    "Class": "Generating.Unit",
                    "Description": None,
                    "Parent Class": None,
                    "Source": "http://www.iec.ch/TC57/CIM#GeneratingUnit",
                    "Match": "exact",
                }
            ],
            "Properties": [
                {
                    "Class": "Generating.Unit",
                    "Property": "IdentifiedObject.name",
                    "Description": None,
                    "Value Type": "StrING",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Transformation": None,
                }
            ],
        },
        id="straightening_entities",
    )


class TestInformationConverter:
    @pytest.mark.parametrize(
        "name, expected",
        [
            ("mycontainer", "mycontainer2"),
            ("mycontainer2", "mycontainer3"),
            ("sran*2@N", "sran*2@N2"),
        ],
    )
    def test_bump_suffix(self, name: str, expected: str) -> None:
        actual = _InformationRulesConverter._bump_suffix(name)

        assert actual == expected

    @pytest.mark.parametrize(
        "multi, expected",
        [
            pytest.param(
                MultiValueTypeInfo(types=[data_types.Integer(), data_types.String()]), data_types.String(), id="IntStr"
            ),
            pytest.param(
                MultiValueTypeInfo(types=[data_types.Float(), data_types.Integer()]), data_types.Double(), id="FloatStr"
            ),
            pytest.param(
                MultiValueTypeInfo(types=[data_types.Boolean(), data_types.Float()]),
                data_types.Double(),
                id="BoolFloat",
            ),
            pytest.param(
                MultiValueTypeInfo(types=[data_types.DateTime(), data_types.Boolean()]),
                data_types.String(),
                id="DatetimeBool as String",
            ),
            pytest.param(
                MultiValueTypeInfo(types=[data_types.Date(), data_types.DateTime()]),
                data_types.DateTime(),
                id="Date and Datetime",
            ),
        ],
    )
    def test_convert_multivalue_type(self, multi: MultiValueTypeInfo, expected: DataType) -> None:
        actual = _InformationRulesConverter.convert_multi_data_type(multi)

        assert actual == expected

    @pytest.mark.parametrize("rules_dict", list(non_compliant_entities()))
    def test_to_compliant_entities(
        self,
        rules_dict: dict[str, dict[str, Any]],
    ) -> None:
        input_rules = ReadRules(rules=InformationInputRules.load(rules_dict), read_context={})
        transformer = VerifyAnyRules(validate=True)
        rules = transformer.transform(input_rules)

        rules = ToCompliantEntities().transform(rules)

        assert rules.classes[0].class_.prefix == "power_or_not"
        assert rules.classes[0].class_.suffix == "Generating_Unit"
        assert rules.properties[0].property_ == "IdentifiedObject_name"
        assert rules.properties[0].class_.suffix == "Generating_Unit"


class TestInformationProperty:
    @pytest.mark.parametrize(
        "raw",
        [
            pytest.param(
                InformationInputProperty(
                    class_="MyAsset",
                    property_="name",
                    value_type="string",
                    max_count=1,
                    instance_source="prefix_16:MyAsset(prefix_16:P&ID)",
                ),
                id="Instance Source with ampersand",
            ),
            pytest.param(
                InformationInputProperty(
                    class_="MyAsset",
                    property_="name",
                    value_type="string",
                    max_count=1,
                    instance_source="prefix_16:MyAsset(prefix_16:State(Previous))",
                ),
                id="Instance Source with parentheses",
            ),
        ],
    )
    def test_rdf_properties(self, raw: InformationInputProperty):
        prop = InformationProperty.model_validate(raw.dump(default_prefix="power"))

        assert isinstance(prop, InformationProperty)

    @pytest.mark.parametrize(
        "raw, expected",
        [
            pytest.param(
                InformationInputProperty(
                    "cdf_cdm:CogniteAsset(version=v1)",
                    "name",
                    "text",
                ),
                ClassEntity(prefix="cdf_cdm", suffix="CogniteAsset", version="v1"),
                id="CogniteAsset name",
            )
        ],
    )
    def test_validate_class_entity(self, raw: InformationInputProperty, expected: ClassEntity) -> None:
        prop = InformationProperty.model_validate(raw.dump(default_prefix="my_space"))

        assert prop.class_ == expected


class TestInformationClass:
    @pytest.mark.parametrize(
        "raw, class_, implements",
        [
            (
                InformationInputClass(
                    class_="WindTurbine",
                    description="Power generating unite",
                    implements="cdf_cdm:CogniteAsset(version=v1)",
                ),
                ClassEntity(prefix="my_space", suffix="WindTurbine"),
                ClassEntity(prefix="cdf_cdm", suffix="CogniteAsset", version="v1"),
            )
        ],
    )
    def test_validate_class_entity(
        self,
        raw: InformationInputClass,
        class_: ClassEntity,
        implements: ClassEntity,
    ) -> None:
        info_class = InformationClass.model_validate(raw.dump(default_prefix="my_space"))

        assert info_class.class_ == class_
        assert isinstance(info_class.implements, list)
        assert info_class.implements[0] == implements
