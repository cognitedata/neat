from collections.abc import Iterable
from typing import Any

import pytest
from _pytest.mark import ParameterSet
from cognite.client import data_modeling as dm

from cognite.neat.rules.importers import DMSImporter
from cognite.neat.rules.models._rules._types import ViewEntity
from cognite.neat.rules.models._rules.base import SheetList
from cognite.neat.rules.models._rules.dms_architect_rules import (
    DMSContainer,
    DMSMetadata,
    DMSProperty,
    DMSRules,
    DMSView,
)
from cognite.neat.rules.models._rules.dms_schema import DMSSchema


def rules_schema_tests_cases() -> Iterable[ParameterSet]:
    yield pytest.param(
        DMSRules(
            metadata=DMSMetadata(
                schema_="complete",
                space="my_space",
                external_id="my_data_model",
                description="DMS data model",
                version="1",
                creator="Alice",
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=SheetList[DMSProperty](
                data=[
                    DMSProperty(
                        class_="WindTurbine",
                        property_="name",
                        value_type="text",
                        container="Asset",
                        container_property="name",
                        view="Asset",
                        view_property="name",
                    ),
                    DMSProperty(
                        class_="WindTurbine",
                        property_="ratedPower",
                        value_type="float64",
                        container="GeneratingUnit",
                        container_property="ratedPower",
                        view="WindTurbine",
                        view_property="ratedPower",
                    ),
                    DMSProperty(
                        class_="WindFarm",
                        property_="WindTurbines",
                        value_type=ViewEntity(suffix="WindTurbine"),
                        relation="multiedge",
                        view="WindFarm",
                        view_property="windTurbines",
                    ),
                ]
            ),
            containers=SheetList[DMSContainer](
                data=[
                    DMSContainer(container="Asset"),
                    DMSContainer(class_="GeneratingUnit", container="GeneratingUnit", constraint="Asset"),
                ]
            ),
            views=SheetList[DMSView](
                data=[
                    DMSView(class_="Asset", view="Asset"),
                    DMSView(class_="WindTurbine", view="WindTurbine", implements=["Asset"]),
                    DMSView(class_="WindFarm", view="WindFarm"),
                ]
            ),
        ),
        DMSSchema(
            spaces=dm.SpaceApplyList(
                [
                    dm.SpaceApply(
                        space="my_space",
                    )
                ]
            ),
            data_models=dm.DataModelApplyList(
                [
                    dm.DataModelApply(
                        space="my_space",
                        external_id="my_data_model",
                        version="1",
                        description="DMS data model Creator: Alice",
                        views=[
                            dm.ViewId(space="my_space", external_id="Asset", version="1"),
                            dm.ViewId(space="my_space", external_id="WindTurbine", version="1"),
                            dm.ViewId(space="my_space", external_id="WindFarm", version="1"),
                        ],
                    )
                ]
            ),
            views=dm.ViewApplyList(
                [
                    dm.ViewApply(
                        space="my_space",
                        external_id="Asset",
                        version="1",
                        properties={
                            "name": dm.MappedPropertyApply(
                                container=dm.ContainerId("my_space", "Asset"), container_property_identifier="name"
                            )
                        },
                    ),
                    dm.ViewApply(
                        space="my_space",
                        external_id="WindTurbine",
                        version="1",
                        implements=[dm.ViewId("my_space", "Asset", "1")],
                        properties={
                            "ratedPower": dm.MappedPropertyApply(
                                container=dm.ContainerId("my_space", "GeneratingUnit"),
                                container_property_identifier="ratedPower",
                            ),
                        },
                    ),
                    dm.ViewApply(
                        space="my_space",
                        external_id="WindFarm",
                        version="1",
                        properties={
                            "windTurbines": dm.MultiEdgeConnectionApply(
                                type=dm.DirectRelationReference(space="my_space", external_id="WindFarm.windTurbines"),
                                source=dm.ViewId(space="my_space", external_id="WindTurbine", version="1"),
                                direction="outwards",
                            )
                        },
                    ),
                ]
            ),
            containers=dm.ContainerApplyList(
                [
                    dm.ContainerApply(
                        space="my_space",
                        external_id="Asset",
                        properties={"name": dm.ContainerProperty(type=dm.Text(), nullable=True)},
                    ),
                    dm.ContainerApply(
                        space="my_space",
                        external_id="GeneratingUnit",
                        properties={
                            "ratedPower": dm.ContainerProperty(type=dm.Float64(), nullable=True),
                        },
                        constraints={"my_space:Asset": dm.RequiresConstraint(dm.ContainerId("my_space", "Asset"))},
                    ),
                ]
            ),
        ),
        id="Two properties, one container, one view",
    )


def valid_rules_tests_cases() -> Iterable[ParameterSet]:
    yield pytest.param(
        {
            "metadata": {
                "schema_": "complete",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "WindTurbine",
                        "property_": "name",
                        "value_type": "text",
                        "container": "sp_core:Asset",
                        "container_property": "name",
                        "view": "sp_core:Asset",
                        "view_property": "name",
                    },
                    {
                        "class_": "WindTurbine",
                        "property_": "ratedPower",
                        "value_type": "float64",
                        "container": "GeneratingUnit",
                        "container_property": "ratedPower",
                        "view": "WindTurbine",
                        "view_property": "ratedPower",
                    },
                ]
            },
            "containers": {
                "data": [
                    {"class_": "Asset", "container": "sp_core:Asset"},
                    {
                        "class_": "WindTurbine",
                        "container": "WindTurbine",
                        "constraint": "sp_core:Asset",
                    },
                ]
            },
            "views": {
                "data": [
                    {"class_": "Asset", "view": "sp_core:Asset"},
                    {
                        "class_": "WindTurbine",
                        "view": "WindTurbine",
                        "implements": "sp_core:Asset",
                    },
                ]
            },
        },
        DMSRules(
            metadata=DMSMetadata(
                schema_="complete",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator=["Anders"],
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=SheetList[DMSProperty](
                data=[
                    DMSProperty(
                        class_="WindTurbine",
                        property_="name",
                        value_type="text",
                        container="sp_core:Asset",
                        container_property="name",
                        view="sp_core:Asset",
                        view_property="name",
                    ),
                    DMSProperty(
                        class_="WindTurbine",
                        property_="ratedPower",
                        value_type="float64",
                        container="GeneratingUnit",
                        container_property="ratedPower",
                        view="WindTurbine",
                        view_property="ratedPower",
                    ),
                ]
            ),
            containers=SheetList[DMSContainer](
                data=[
                    DMSContainer(container="sp_core:Asset", class_="Asset"),
                    DMSContainer(class_="WindTurbine", container="WindTurbine", constraint="sp_core:Asset"),
                ]
            ),
            views=SheetList[DMSView](
                data=[
                    DMSView(view="sp_core:Asset", class_="Asset"),
                    DMSView(class_="WindTurbine", view="WindTurbine", implements=["sp_core:Asset"]),
                ]
            ),
        ),
        id="Two properties, two containers, two views. Primary data types, no relations.",
    )

    yield pytest.param(
        {
            "metadata": {
                "schema_": "complete",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "Plant",
                        "property_": "name",
                        "value_type": "text",
                        "container": "Asset",
                        "container_property": "name",
                        "view": "Asset",
                        "view_property": "name",
                    },
                    {
                        "class_": "Plant",
                        "property_": "generators",
                        "relation": "multiedge",
                        "value_type": "Generator",
                        "view": "Plant",
                        "view_property": "generators",
                    },
                    {
                        "class_": "Plant",
                        "property_": "reservoir",
                        "relation": "direct",
                        "value_type": "Reservoir",
                        "container": "Asset",
                        "container_property": "child",
                        "view": "Plant",
                        "view_property": "reservoir",
                    },
                    {
                        "class_": "Generator",
                        "property_": "name",
                        "value_type": "text",
                        "container": "Asset",
                        "container_property": "name",
                        "view": "Asset",
                        "view_property": "name",
                    },
                    {
                        "class_": "Reservoir",
                        "property_": "name",
                        "value_type": "text",
                        "container": "Asset",
                        "container_property": "name",
                        "view": "Asset",
                        "view_property": "name",
                    },
                ]
            },
            "containers": {
                "data": [
                    {"class_": "Asset", "container": "Asset"},
                    {
                        "class_": "Plant",
                        "container": "Plant",
                        "constraint": "Asset",
                    },
                ]
            },
            "views": {
                "data": [
                    {"class_": "Asset", "view": "Asset"},
                    {"class_": "Plant", "view": "Plant", "implements": "Asset"},
                    {"class_": "Generator", "view": "Generator", "implements": "Asset"},
                    {"class_": "Reservoir", "view": "Reservoir", "implements": "Asset"},
                ]
            },
        },
        DMSRules(
            metadata=DMSMetadata(
                schema_="complete",
                space="my_space",
                external_id="my_data_model",
                version="1",
                creator=["Anders"],
                created="2021-01-01T00:00:00",
                updated="2021-01-01T00:00:00",
            ),
            properties=SheetList[DMSProperty](
                data=[
                    DMSProperty(
                        class_="Plant",
                        property_="name",
                        value_type="text",
                        container="Asset",
                        container_property="name",
                        view="Asset",
                        view_property="name",
                    ),
                    DMSProperty(
                        class_="Plant",
                        property_="generators",
                        value_type=ViewEntity(suffix="Generator"),
                        relation="multiedge",
                        view="Plant",
                        view_property="generators",
                    ),
                    DMSProperty(
                        class_="Plant",
                        property_="reservoir",
                        value_type=ViewEntity(suffix="Reservoir"),
                        relation="direct",
                        container="Asset",
                        container_property="child",
                        view="Plant",
                        view_property="reservoir",
                    ),
                    DMSProperty(
                        class_="Generator",
                        property_="name",
                        value_type="text",
                        container="Asset",
                        container_property="name",
                        view="Asset",
                        view_property="name",
                    ),
                    DMSProperty(
                        class_="Reservoir",
                        property_="name",
                        value_type="text",
                        container="Asset",
                        container_property="name",
                        view="Asset",
                        view_property="name",
                    ),
                ]
            ),
            containers=SheetList[DMSContainer](
                data=[
                    DMSContainer(container="Asset", class_="Asset"),
                    DMSContainer(class_="Plant", container="Plant", constraint="Asset"),
                ]
            ),
            views=SheetList[DMSView](
                data=[
                    DMSView(view="Asset", class_="Asset"),
                    DMSView(class_="Plant", view="Plant", implements=["Asset"]),
                    DMSView(class_="Generator", view="Generator", implements=["Asset"]),
                    DMSView(class_="Reservoir", view="Reservoir", implements=["Asset"]),
                ]
            ),
        ),
        id="Five properties, two containers, four views. Direct relations and Multiedge.",
    )


def invalid_rules_test_cases() -> Iterable[ParameterSet]:
    yield pytest.param(
        {},
        "missing",
        id="Empty rules",
    )
    # this does not raise the error
    # yield pytest.param(
    #         },
    #             "data": [
    #                 },
    #         },
    #     },
    #     "not a valid value type for a property",
    yield pytest.param(
        {
            "metadata": {
                "schema_": "partial",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "WindTurbine",
                        "property_": "maxPower",
                        "value_type": "float64",
                        "is_list": "false",
                        "container": "GeneratingUnit",
                        "container_property": "maxPower",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                    },
                    {
                        "class_": "HydroGenerator",
                        "property_": "maxPower",
                        "value_type": "float32",
                        "container": "GeneratingUnit",
                        "container_property": "maxPower",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                    },
                ]
            },
            "views": {"data": [{"view": "WindTurbine", "class_": "WindTurbine"}]},
        },
        "with different value types",
        id="Inconsistent container definition value type",
    )
    yield pytest.param(
        {
            "metadata": {
                "schema_": "partial",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "WindTurbine",
                        "property_": "maxPower",
                        "value_type": "float64",
                        "is_list": "true",
                        "container": "GeneratingUnit",
                        "container_property": "maxPower",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                    },
                    {
                        "class_": "HydroGenerator",
                        "property_": "maxPower",
                        "value_type": "float64",
                        "is_list": "false",
                        "container": "GeneratingUnit",
                        "container_property": "maxPower",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                    },
                ]
            },
            "views": {"data": [{"view": "WindTurbine", "class_": "WindTurbine"}]},
        },
        "different list definitions",
        id="Inconsistent container definition isList",
    )
    yield pytest.param(
        {
            "metadata": {
                "schema_": "partial",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "WindTurbine",
                        "property_": "maxPower",
                        "value_type": "float64",
                        "nullable": "true",
                        "container": "GeneratingUnit",
                        "container_property": "maxPower",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                    },
                    {
                        "class_": "HydroGenerator",
                        "property_": "maxPower",
                        "value_type": "float64",
                        "nullable": "false",
                        "container": "GeneratingUnit",
                        "container_property": "maxPower",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                    },
                ]
            },
            "views": {"data": [{"view": "WindTurbine", "class_": "WindTurbine"}]},
        },
        "different nullable definitions",
        id="Inconsistent container definition nullable",
    )
    yield pytest.param(
        {
            "metadata": {
                "schema_": "partial",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "WindTurbine",
                        "property_": "name",
                        "value_type": "text",
                        "container": "GeneratingUnit",
                        "container_property": "name",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                        "index": "name",
                    },
                    {
                        "class_": "HydroGenerator",
                        "property_": "name",
                        "value_type": "text",
                        "container": "GeneratingUnit",
                        "container_property": "name",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                        "index": "name_index",
                    },
                ]
            },
            "views": {"data": [{"view": "WindTurbine", "class_": "WindTurbine"}]},
        },
        "defined with different index definitions",
        id="Inconsistent container definition index",
    )
    yield pytest.param(
        {
            "metadata": {
                "schema_": "partial",
                "space": "my_space",
                "external_id": "my_data_model",
                "version": "1",
                "creator": "Anders",
                "created": "2021-01-01T00:00:00",
                "updated": "2021-01-01T00:00:00",
            },
            "properties": {
                "data": [
                    {
                        "class_": "WindTurbine",
                        "property_": "name",
                        "value_type": "text",
                        "container": "GeneratingUnit",
                        "container_property": "name",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                        "constraint": "unique_name",
                    },
                    {
                        "class_": "HydroGenerator",
                        "property_": "name",
                        "value_type": "text",
                        "container": "GeneratingUnit",
                        "container_property": "name",
                        "view": "sp_core:Asset",
                        "view_property": "maxPower",
                        "constraint": "name",
                    },
                ]
            },
            "views": {"data": [{"view": "WindTurbine", "class_": "WindTurbine"}]},
        },
        "different unique constraint definitions",
        id="Inconsistent container definition constraint",
    )


class TestDMSRules:
    def test_load_valid_alice_rules(self, alice_spreadsheet: dict[str, dict[str, Any]]) -> None:
        valid_rules = DMSRules.model_validate(alice_spreadsheet)

        assert isinstance(valid_rules, DMSRules)

        sample_expected_properties = {"WindTurbine.name", "WindFarm.windTurbines", "CircuitBreaker.voltage"}
        missing = sample_expected_properties - {f"{prop.class_}.{prop.property_}" for prop in valid_rules.properties}
        assert not missing, f"Missing properties: {missing}"

    @pytest.mark.parametrize("raw, expected_rules", list(valid_rules_tests_cases()))
    def test_load_valid_rules(self, raw: dict[str, dict[str, Any]], expected_rules: DMSRules) -> None:
        valid_rules = DMSRules.model_validate(raw)
        assert valid_rules.model_dump() == expected_rules.model_dump()

    @pytest.mark.parametrize("raw, expected_msg", list(invalid_rules_test_cases()))
    def test_load_invalid_rules(self, raw: dict[str, dict[str, Any]], expected_msg: str) -> None:
        with pytest.raises(ValueError) as e:
            DMSRules.model_validate(raw)

        assert expected_msg in str(e.value)

    def test_alice_to_and_from_DMS(self, alice_rules: DMSRules) -> None:
        schema = alice_rules.as_schema()
        rules = alice_rules.copy()
        recreated_rules = DMSImporter(schema).to_rules()

        # Sorting to avoid order differences
        recreated_rules.properties = SheetList[DMSProperty](
            data=sorted(recreated_rules.properties, key=lambda p: (p.class_, p.property_))
        )
        rules.properties = SheetList[DMSProperty](data=sorted(rules.properties, key=lambda p: (p.class_, p.property_)))
        recreated_rules.containers = SheetList[DMSContainer](
            data=sorted(recreated_rules.containers, key=lambda c: c.container)
        )
        rules.containers = SheetList[DMSContainer](data=sorted(rules.containers, key=lambda c: c.container))
        recreated_rules.views = SheetList[DMSView](data=sorted(recreated_rules.views, key=lambda v: v.view))
        rules.views = SheetList[DMSView](data=sorted(rules.views, key=lambda v: v.view))

        # Sorting out dates
        recreated_rules.metadata.created = rules.metadata.created
        recreated_rules.metadata.updated = rules.metadata.updated

        assert recreated_rules.model_dump() == rules.model_dump()

    @pytest.mark.parametrize("rules, expected_schema", rules_schema_tests_cases())
    def test_as_schema(self, rules: DMSRules, expected_schema: DMSSchema) -> None:
        actual_schema = rules.as_schema()

        assert actual_schema.spaces.dump() == expected_schema.spaces.dump()
        actual_schema.data_models[0].views = sorted(actual_schema.data_models[0].views, key=lambda v: v.external_id)
        expected_schema.data_models[0].views = sorted(expected_schema.data_models[0].views, key=lambda v: v.external_id)
        assert actual_schema.data_models[0].dump() == expected_schema.data_models[0].dump()
        assert actual_schema.containers.dump() == expected_schema.containers.dump()

        actual_schema.views = dm.ViewApplyList(sorted(actual_schema.views, key=lambda v: v.external_id))
        expected_schema.views = dm.ViewApplyList(sorted(expected_schema.views, key=lambda v: v.external_id))
        assert actual_schema.views.dump() == expected_schema.views.dump()
