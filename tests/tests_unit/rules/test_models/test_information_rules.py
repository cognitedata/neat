from datetime import datetime
from typing import Any

import pytest
from cognite.client import data_modeling as dm

from cognite.neat.issues import NeatError
from cognite.neat.issues.errors import NeatValueError, ResourceNotDefinedError
from cognite.neat.rules.models import DMSRules, SheetList, data_types
from cognite.neat.rules.models._constants import DMS_CONTAINER_PROPERTY_SIZE_LIMIT
from cognite.neat.rules.models.data_types import DataType, String
from cognite.neat.rules.models.entities import ClassEntity, MultiValueTypeInfo
from cognite.neat.rules.models.information import (
    InformationClass,
    InformationRules,
    InformationRulesInput,
)
from cognite.neat.rules.models.information._converter import _InformationRulesConverter
from cognite.neat.rules.models.information._rules_input import (
    InformationClassInput,
    InformationMetadataInput,
    InformationPropertyInput,
)


def case_insensitive_value_types():
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
                "schema": "complete",
                "creator": "Jon, Emma, David",
                "namespace": "http://purl.org/cognite/power2consumer",
                "prefix": "power",
                "created": datetime(2024, 2, 9, 0, 0),
                "updated": datetime(2024, 2, 9, 0, 0),
                "version": "0.1.0",
                "title": "Power to Consumer Data Model",
                "license": "CC-BY 4.0",
                "rights": "Free for use",
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


def invalid_domain_rules_cases():
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
                "schema": "complete",
                "creator": "Jon, Emma, David",
                "namespace": "http://purl.org/cognite/power2consumer",
                "prefix": "power",
                "created": datetime(2024, 2, 9, 0, 0),
                "updated": datetime(2024, 2, 9, 0, 0),
                "version": "0.1.0",
                "title": "Power to Consumer Data Model",
                "license": "CC-BY 4.0",
                "rights": "Free for use",
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
                    "Value Type": "string",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Transformation": ":GeneratingUnit(cim:name)",
                }
            ],
        },
        NeatValueError("Invalid RDF Path: ':GeneratingUnit(cim:name)'"),
        id="missing_rule",
    )


def incomplete_rules_case():
    yield pytest.param(
        {
            "Metadata": {
                "role": "information architect",
                "schema": "complete",
                "creator": "Jon, Emma, David",
                "namespace": "http://purl.org/cognite/power2consumer",
                "prefix": "power",
                "created": datetime(2024, 2, 9, 0, 0),
                "updated": datetime(2024, 2, 9, 0, 0),
                "version": "0.1.0",
                "title": "Power to Consumer Data Model",
                "license": "CC-BY 4.0",
                "rights": "Free for use",
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
                    "Class": "GeneratingUnit2",
                    "Property": "name",
                    "Description": None,
                    "Value Type": "string",
                    "Min Count": 1,
                    "Max Count": 1.0,
                    "Default": None,
                    "Source": None,
                    "MatchType": None,
                    "Rule Type": "rdfpath",
                    "Rule": "cim:GeneratingUnit",
                }
            ],
        },
        ResourceNotDefinedError[ClassEntity](
            ClassEntity(prefix="power", suffix="GeneratingUnit2"), "class", "Classes sheet"
        ),
        id="missing_rule",
    )


class TestInformationRules:
    def test_load_valid_jon_rules(self, david_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = InformationRules.model_validate(david_spreadsheet)

        assert isinstance(valid_rules, InformationRules)

        sample_expected_properties = {
            "power:WindTurbine.manufacturer",
            "power:Substation.secondaryPowerLine",
            "power:WindFarm.exportCable",
        }
        missing = sample_expected_properties - {f"{prop.class_}.{prop.property_}" for prop in valid_rules.properties}
        assert not missing, f"Missing properties: {missing}"

    @pytest.mark.parametrize("invalid_rules, expected_exception", list(invalid_domain_rules_cases()))
    def test_invalid_rules(self, invalid_rules: dict[str, dict[str, Any]], expected_exception: NeatError) -> None:
        with pytest.raises(ValueError) as e:
            InformationRules.model_validate(invalid_rules)
        errors = NeatError.from_pydantic_errors(e.value.errors())
        assert len(errors) == 1
        assert errors[0] == expected_exception

    @pytest.mark.parametrize("incomplete_rules, expected_exception", list(incomplete_rules_case()))
    def test_incomplete_rules(self, incomplete_rules: dict[str, dict[str, Any]], expected_exception: NeatError) -> None:
        with pytest.raises(ValueError) as e:
            InformationRules.model_validate(incomplete_rules)
        errors = NeatError.from_pydantic_errors(e.value.errors())
        assert errors[0] == expected_exception

    @pytest.mark.parametrize("rules, expected_exception", list(case_insensitive_value_types()))
    def test_case_insensitivity(self, rules: dict[str, dict[str, Any]], expected_exception: DataType) -> None:
        assert InformationRules.model_validate(rules).properties.data[0].value_type == expected_exception

    def test_david_as_dms(self, david_spreadsheet: dict[str, dict[str, Any]]) -> None:
        david_rules = InformationRules.model_validate(david_spreadsheet)
        dms_rules = david_rules.as_dms_rules()

        assert isinstance(dms_rules, DMSRules)

    def test_olav_as_dms(self, olav_rules: InformationRules) -> None:
        olav_rules_copy = olav_rules.model_copy(deep=True)
        # Todo: Remove this line when Olav's Information .xlsx file is available
        new_classes = SheetList[InformationClass](data=[])
        for cls_ in olav_rules_copy.classes:
            if cls_.class_.versioned_id == "power_analytics:GeoLocation":
                continue
            elif cls_.class_.versioned_id in ("power_analytics:Point", "power_analytics:Polygon"):
                cls_.parent = None
            new_classes.append(cls_)
        olav_rules_copy.classes = new_classes
        ## End of temporary code

        dms_rules = olav_rules_copy.as_dms_rules()

        assert isinstance(dms_rules, DMSRules)
        schema = dms_rules.as_schema()

        wind_turbine = next((view for view in schema.views.values() if view.external_id == "WindTurbine"), None)
        assert wind_turbine is not None
        expected_containers = {
            dm.ContainerId("power", "GeneratingUnit"),
            dm.ContainerId("power", "WindTurbine"),
            dm.ContainerId("power_analytics", "WindTurbine"),
        }
        missing = expected_containers - wind_turbine.referenced_containers()
        assert not missing, f"Missing containers: {missing}"
        extra = wind_turbine.referenced_containers() - expected_containers
        assert not extra, f"Extra containers: {extra}"

        wind_farm = next((view for view in schema.views.values() if view.external_id == "WindFarm"), None)
        assert wind_farm is not None
        expected_containers = {dm.ContainerId("power", "EnergyArea"), dm.ContainerId("power_analytics", "WindFarm")}
        missing = expected_containers - wind_farm.referenced_containers()
        assert not missing, f"Missing containers: {missing}"
        extra = wind_farm.referenced_containers() - expected_containers
        assert not extra, f"Extra containers: {extra}"

        point = next((view for view in schema.views.values() if view.external_id == "Point"), None)
        assert point is not None
        assert point.implements == [dm.ViewId("power", "Point", "0.1.0")]

        polygon = next((view for view in schema.views.values() if view.external_id == "Polygon"), None)
        assert polygon is not None
        assert polygon.implements == [dm.ViewId("power", "Polygon", "0.1.0")]


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

    def test_svein_harald_information_as_dms(self, svein_harald_information_rules: InformationRules) -> None:
        expected = {
            "ArrayCable": {"PowerLine"},
            "DistributionLine": {"PowerLine"},
            "DistributionSubstation": {"Substation"},
            "ElectricCarCharger": {"EnergyConsumer"},
            "ExportCable": {"PowerLine"},
            "MultiLineString": {"GeoLocation"},
            "OffshoreSubstation": {"Substation"},
            "OnshoreSubstation": {"TransmissionSubstation"},
            "Point": {"GeoLocation"},
            "Polygon": {"GeoLocation"},
            "Transmission": {"PowerLine"},
            "TransmissionSubstation": {"Substation"},
            "WindFarm": {"EnergyArea"},
            "WindTurbine": {"GeneratingUnit"},
        }

        dms_rules = svein_harald_information_rules.as_dms_rules()

        assert isinstance(dms_rules, DMSRules)
        assert dms_rules.last is not None
        actual = {
            view.view.external_id: {parent.external_id for parent in view.implements}
            for view in dms_rules.last.views
            if view.implements
        }

        assert actual == expected

    def test_convert_above_container_limit(self) -> None:
        info = InformationRulesInput(
            metadata=InformationMetadataInput(
                schema_="complete",
                prefix="bad_model",
                namespace="http://purl.org/cognite/bad_model",
                name="Bad Model",
                version="0.1.0",
                creator="Anders",
            ),
            classes=[InformationClassInput(class_="MassiveClass")],
            properties=[
                InformationPropertyInput(
                    class_="MassiveClass",
                    property_=f"property_{no}",
                    value_type="string",
                )
                for no in range(DMS_CONTAINER_PROPERTY_SIZE_LIMIT + 1)
            ],
        ).as_rules()

        dms_rules = info.as_dms_rules()

        assert len(dms_rules.containers) == 2


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
        actual = _InformationRulesConverter.convert_multi_value_type(multi)

        assert actual == expected
