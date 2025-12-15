import pytest
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat._data_model._analysis import ResourceSource, ValidationResources
from cognite.neat._data_model.models.dms import ViewCorePropertyRequest, ViewReference, ViewRequest
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._references import ContainerReference
from tests.data.snapshots.catalog import Catalog


@pytest.fixture(scope="module")
def scenarios() -> dict[str, ValidationResources]:
    catalog = Catalog()
    scenarios = {
        "bi-directional-with-cdm": catalog.load_scenario(
            "bi_directional_connections",
            cdf_scenario_name="cdm",
            modus_operandi="additive",
            include_cdm=True,
            format="validation-resource",
        ),
        "bi-directional-rebuild": catalog.load_scenario(
            "bi_directional_connections",
            cdf_scenario_name="cdm",
            modus_operandi="rebuild",
            include_cdm=True,
            format="validation-resource",
        ),
    }
    return scenarios


class TestValidationResourcesSelectView:
    @pytest.mark.parametrize(
        "scenario,view_ref,property_,source,expected_found",
        [
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="not-existent", external_id="DoesNotExist", version="v1"),
                None,
                "auto",
                False,
                id="view not found",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                None,
                "auto",
                True,
                id="local view found in additive mode",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="cdf_cdm", external_id="CogniteDescribable", version="v1"),
                None,
                "auto",
                True,
                id="cdm view found in additive mode",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                "name",
                "auto",
                True,
                id="local view found with property filter",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                "nonexistent_property",
                "auto",
                True,
                id="local view returned even when property not found",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                None,
                "merged",
                True,
                id="source merged returns view from merged",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                None,
                "cdf",
                False,
                id="source cdf returns none for local view",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="cdf_cdm", external_id="CogniteDescribable", version="v1"),
                None,
                "cdf",
                True,
                id="source cdf returns view from cdf",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                None,
                "both",
                True,
                id="source both returns merged view",
            ),
            pytest.param(
                "bi-directional-rebuild",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                None,
                "auto",
                True,
                id="rebuild mode returns local view only",
            ),
        ],
    )
    def test_select_view(
        self,
        scenario: str,
        view_ref: ViewReference,
        property_: str | None,
        source: ResourceSource,
        expected_found: bool,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        resources = scenarios[scenario]
        view_request = resources.select_view(
            view_ref=view_ref,
            property_=property_,
            source=source,
        )
        if expected_found:
            assert view_request is not None
            assert isinstance(view_request, ViewRequest)
            assert view_request.as_reference() == view_ref
        else:
            assert view_request is None


class TestValidationResourcesSelectContainer:
    @pytest.mark.parametrize(
        "scenario,container_ref,property_,source,expected_found",
        [
            pytest.param(
                "bi-directional-with-cdm",
                ContainerReference(space="not-existent", external_id="DoesNotExist"),
                None,
                "auto",
                False,
                id="container not found",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ContainerReference(space="my_space", external_id="SourceContainer"),
                None,
                "auto",
                True,
                id="local container found in additive mode",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ContainerReference(space="cdf_cdm", external_id="CogniteDescribable"),
                None,
                "auto",
                True,
                id="cdm container found in additive mode",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ContainerReference(space="my_space", external_id="SourceContainer"),
                "nameStorage",
                "auto",
                True,
                id="container found with property filter",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ContainerReference(space="my_space", external_id="SourceContainer"),
                "nonexistent_property",
                "auto",
                True,
                id="container returned even when property not found",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ContainerReference(space="my_space", external_id="SourceContainer"),
                None,
                "merged",
                True,
                id="source merged returns container from merged",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ContainerReference(space="my_space", external_id="SourceContainer"),
                None,
                "cdf",
                False,
                id="source cdf returns none for local container",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ContainerReference(space="cdf_cdm", external_id="CogniteDescribable"),
                None,
                "cdf",
                True,
                id="source cdf returns container from cdf",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ContainerReference(space="my_space", external_id="SourceContainer"),
                None,
                "both",
                True,
                id="source both returns merged container",
            ),
            pytest.param(
                "bi-directional-rebuild",
                ContainerReference(space="my_space", external_id="SourceContainer"),
                None,
                "auto",
                True,
                id="rebuild mode returns local container only",
            ),
        ],
    )
    def test_select_container(
        self,
        scenario: str,
        container_ref: ContainerReference,
        property_: str | None,
        source: ResourceSource,
        expected_found: bool,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        resources = scenarios[scenario]
        container_request = resources.select_container(
            container_ref=container_ref,
            property_=property_,
            source=source,
        )
        if expected_found:
            assert container_request is not None
            assert isinstance(container_request, ContainerRequest)
        else:
            assert container_request is None


class TestValidationResourcesAncestors:
    @pytest.mark.parametrize(
        "scenario,view_ref,expected_ancestors",
        [
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                [],
                id="view without implements has no ancestors",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="DescendantView", version="v1"),
                [ViewReference(space="my_space", external_id="AncestorView", version="v1")],
                id="view with implements has ancestors",
            ),
        ],
    )
    def test_view_ancestors(
        self,
        scenario: str,
        view_ref: ViewReference,
        expected_ancestors: list[ViewReference],
        scenarios: dict[str, ValidationResources],
    ) -> None:
        resources = scenarios[scenario]
        ancestors = resources.view_ancestors(view_ref)
        assert ancestors == expected_ancestors

    @pytest.mark.parametrize(
        "scenario,view_ref,expected_has_ancestor_count",
        [
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                0,
                id="view without implements in ancestors_by_view",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="DescendantView", version="v1"),
                1,
                id="view with implements in ancestors_by_view",
            ),
        ],
    )
    def test_ancestors_by_view(
        self,
        scenario: str,
        view_ref: ViewReference,
        expected_has_ancestor_count: int,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        resources = scenarios[scenario]
        ancestors_mapping = resources.ancestors_by_view
        assert view_ref in ancestors_mapping
        assert len(ancestors_mapping[view_ref]) == expected_has_ancestor_count

    @pytest.mark.parametrize(
        "scenario,offspring,ancestor,expected",
        [
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="DescendantView", version="v1"),
                ViewReference(space="my_space", external_id="AncestorView", version="v1"),
                True,
                id="is_ancestor returns true for valid ancestor",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                ViewReference(space="my_space", external_id="AncestorView", version="v1"),
                False,
                id="is_ancestor returns false for non-ancestor",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="AncestorView", version="v1"),
                ViewReference(space="my_space", external_id="DescendantView", version="v1"),
                False,
                id="is_ancestor returns false for descendant",
            ),
        ],
    )
    def test_is_ancestor(
        self,
        scenario: str,
        offspring: ViewReference,
        ancestor: ViewReference,
        expected: bool,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        resources = scenarios[scenario]
        result = resources.is_ancestor(offspring, ancestor)
        assert result == expected


class TestValidationResourcesProperties:
    @pytest.mark.parametrize(
        "scenario,view_ref,expected_property_count",
        [
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                6,
                id="view with properties",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="ViewWithoutProperties", version="v1"),
                0,
                id="view without properties",
            ),
        ],
    )
    def test_properties_by_view(
        self,
        scenario: str,
        view_ref: ViewReference,
        expected_property_count: int,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        resources = scenarios[scenario]
        properties_mapping = resources.properties_by_view
        assert view_ref in properties_mapping
        assert len(properties_mapping[view_ref]) == expected_property_count

    def test_properties_by_view_inherits_from_ancestors(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that properties_by_view includes inherited properties from ancestors"""
        resources = scenarios["bi-directional-with-cdm"]
        descendant_ref = ViewReference(space="my_space", external_id="DescendantView", version="v1")
        ancestor_ref = ViewReference(space="my_space", external_id="AncestorView", version="v1")

        properties_mapping = resources.properties_by_view

        # Get ancestor's properties
        ancestor_props = properties_mapping.get(ancestor_ref, {})
        descendant_props = properties_mapping.get(descendant_ref, {})

        assert set(ancestor_props.keys()).issubset(set(descendant_props.keys())), (
            "Descendant view does not include all properties from ancestor view"
        )

    def test_referenced_containers(self, scenarios: dict[str, ValidationResources]) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        actual_referenced = resources.referenced_containers

        expected_references = {
            prop.container
            for view in resources.local.views.values()
            for prop in view.properties.values()
            if isinstance(prop, ViewCorePropertyRequest)
        }
        # The bi-directional scenario has references to containers in its properties
        assert actual_referenced == expected_references


class TestValidationResourcesReverseToDirectMapping:
    def test_reverse_to_direct_mapping(
        self, scenarios: dict[str, ValidationResources], data_regression: DataRegressionFixture
    ) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        mapping = resources.reverse_to_direct_mapping
        assert len(mapping) > 0, "Expected non-empty reverse to direct mapping"

        serializable = {
            f"{view_ref!s}.{prop!s}": f"{target_view_ref!s},{target_prop!s}"
            for (view_ref, prop), (target_view_ref, target_prop) in mapping.items()
        }
        data_regression.check(serializable)


class TestValidationResourcesConnectionEndNodeTypes:
    def test_connection_end_node_types(
        self, scenarios: dict[str, ValidationResources], data_regression: DataRegressionFixture
    ) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        end_node_types = resources.connection_end_node_types

        assert len(end_node_types) > 0, "Expected non-empty connection end node types"

        serializable = {
            f"{view_ref!s}.{prop!s}": f"{target_view_ref!s}" if target_view_ref is not None else None
            for (view_ref, prop), target_view_ref in end_node_types.items()
        }
        data_regression.check(serializable)
