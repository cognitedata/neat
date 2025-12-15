import pytest

from cognite.neat._data_model._analysis import ResourceSource, ValidationResources
from cognite.neat._data_model.models.dms import ViewReference, ViewRequest
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
        "ai-readiness-with-cdm": catalog.load_scenario(
            "ai_readiness",
            cdf_scenario_name="cdm",
            modus_operandi="additive",
            include_cdm=True,
            format="validation-resource",
        ),
        "uncategorized-validators": catalog.load_scenario(
            "uncategorized_validators",
            cdf_scenario_name="for_validators",
            modus_operandi="additive",
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


class TestValidationResourcesResolveResourceSources:
    @pytest.mark.parametrize(
        "scenario,resource_ref,source,expected_check_merged,expected_check_cdf",
        [
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                "auto",
                True,
                True,
                id="additive mode auto checks both for local resource",
            ),
            pytest.param(
                "bi-directional-rebuild",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                "auto",
                True,
                False,
                id="rebuild mode auto checks only merged for local resource",
            ),
            pytest.param(
                "bi-directional-rebuild",
                ViewReference(space="cdf_cdm", external_id="CogniteDescribable", version="v1"),
                "auto",
                True,
                True,
                id="rebuild mode auto checks both for non-local resource",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                "merged",
                True,
                False,
                id="merged source checks only merged",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                "cdf",
                False,
                True,
                id="cdf source checks only cdf",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                "both",
                True,
                True,
                id="both source checks merged and cdf",
            ),
        ],
    )
    def test_resolve_resource_sources(
        self,
        scenario: str,
        resource_ref: ViewReference | ContainerReference,
        source: ResourceSource,
        expected_check_merged: bool,
        expected_check_cdf: bool,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        resources = scenarios[scenario]
        check_merged, check_cdf = resources._resolve_resource_sources(resource_ref, source)
        assert check_merged == expected_check_merged
        assert check_cdf == expected_check_cdf

    def test_resolve_resource_sources_invalid_source(self, scenarios: dict[str, ValidationResources]) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        view_ref = ViewReference(space="my_space", external_id="SourceView", version="v1")
        with pytest.raises(RuntimeError, match="Unknown source"):
            resources._resolve_resource_sources(view_ref, "invalid")  # type: ignore[arg-type]


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

    def test_view_ancestors_with_source_parameter(self, scenarios: dict[str, ValidationResources]) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        view_ref = ViewReference(space="my_space", external_id="DescendantView", version="v1")
        ancestors = resources.view_ancestors(view_ref, source="merged")
        assert ancestors == [ViewReference(space="my_space", external_id="AncestorView", version="v1")]

    @pytest.mark.parametrize(
        "scenario,view_ref,expected_has_ancestors",
        [
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                False,
                id="view without implements in ancestors_by_view",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="DescendantView", version="v1"),
                True,
                id="view with implements in ancestors_by_view",
            ),
        ],
    )
    def test_ancestors_by_view(
        self,
        scenario: str,
        view_ref: ViewReference,
        expected_has_ancestors: bool,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        resources = scenarios[scenario]
        ancestors_mapping = resources.ancestors_by_view
        assert view_ref in ancestors_mapping
        if expected_has_ancestors:
            assert len(ancestors_mapping[view_ref]) > 0
        else:
            assert len(ancestors_mapping[view_ref]) == 0

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
        "scenario,view_ref,expected_has_properties",
        [
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="SourceView", version="v1"),
                True,
                id="view with properties",
            ),
            pytest.param(
                "bi-directional-with-cdm",
                ViewReference(space="my_space", external_id="ViewWithoutProperties", version="v1"),
                False,
                id="view without properties",
            ),
        ],
    )
    def test_properties_by_view(
        self,
        scenario: str,
        view_ref: ViewReference,
        expected_has_properties: bool,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        resources = scenarios[scenario]
        properties_mapping = resources.properties_by_view
        assert view_ref in properties_mapping
        if expected_has_properties:
            assert len(properties_mapping[view_ref]) > 0
        else:
            assert len(properties_mapping[view_ref]) == 0

    def test_properties_by_view_inherits_from_ancestors(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that properties_by_view includes inherited properties from ancestors"""
        resources = scenarios["bi-directional-with-cdm"]
        descendant_ref = ViewReference(space="my_space", external_id="DescendantView", version="v1")
        ancestor_ref = ViewReference(space="my_space", external_id="AncestorView", version="v1")

        properties_mapping = resources.properties_by_view

        # Get ancestor's properties
        ancestor_props = properties_mapping.get(ancestor_ref, {})
        descendant_props = properties_mapping.get(descendant_ref, {})

        # Descendant should have ancestor's properties
        for prop_name in ancestor_props:
            # The property might be overridden in descendant
            assert prop_name in descendant_props

    def test_referenced_containers(self, scenarios: dict[str, ValidationResources]) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        referenced = resources.referenced_containers
        assert isinstance(referenced, set)
        # Should contain at least the local containers used in views
        assert len(referenced) > 0
        # Verify the type of elements
        for container_ref in referenced:
            assert isinstance(container_ref, ContainerReference)


class TestValidationResourcesReverseToDirectMapping:
    def test_reverse_to_direct_mapping(self, scenarios: dict[str, ValidationResources]) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        mapping = resources.reverse_to_direct_mapping
        assert isinstance(mapping, dict)
        # The bi-directional scenario has reverse direct relations
        assert len(mapping) > 0

        # Verify the structure
        for key, value in mapping.items():
            assert isinstance(key, tuple)
            assert len(key) == 2
            assert isinstance(key[0], ViewReference)
            assert isinstance(key[1], str)

            assert isinstance(value, tuple)
            assert len(value) == 2
            assert isinstance(value[0], ViewReference)


class TestValidationResourcesConnectionEndNodeTypes:
    def test_connection_end_node_types(self, scenarios: dict[str, ValidationResources]) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        end_node_types = resources.connection_end_node_types
        assert isinstance(end_node_types, dict)
        # Should have connection end node types for the test data
        assert len(end_node_types) > 0

        # Verify structure
        for key in end_node_types:
            assert isinstance(key, tuple)
            assert len(key) == 2
            assert isinstance(key[0], ViewReference)
            assert isinstance(key[1], str)

    def test_connection_end_node_types_includes_direct_relations(
        self, scenarios: dict[str, ValidationResources]
    ) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        end_node_types = resources.connection_end_node_types

        # Check that direct relation from SourceView is included
        source_view = ViewReference(space="my_space", external_id="SourceView", version="v1")
        has_direct_from_source = any(key[0] == source_view for key in end_node_types)
        assert has_direct_from_source

    def test_connection_end_node_types_includes_reverse_relations(
        self, scenarios: dict[str, ValidationResources]
    ) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        end_node_types = resources.connection_end_node_types

        # Check that reverse relations from TargetView are included
        target_view = ViewReference(space="my_space", external_id="TargetView", version="v1")
        has_reverse_from_target = any(key[0] == target_view for key in end_node_types)
        assert has_reverse_from_target

    def test_connection_end_node_types_includes_edge_properties(
        self, scenarios: dict[str, ValidationResources]
    ) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        end_node_types = resources.connection_end_node_types

        # Check that edge connection from SourceView is included
        source_view = ViewReference(space="my_space", external_id="SourceView", version="v1")
        has_edge_from_source = any(key[0] == source_view and key[1] == "edgeConnection" for key in end_node_types)
        assert has_edge_from_source

    def test_connection_end_node_types_includes_implicit_direct_relations(
        self, scenarios: dict[str, ValidationResources]
    ) -> None:
        """Test that direct relations without explicit source (pointing to container property) are
        included with None value"""
        resources = scenarios["uncategorized-validators"]
        end_node_types = resources.connection_end_node_types

        # Look for entries where value is None (implicit direct relations)
        implicit_relations = [key for key, value in end_node_types.items() if value is None]
        # The uncategorized-validators test data has directToNowhere which should result in None
        assert len(implicit_relations) > 0


class TestValidationResourcesMergedDataModel:
    def test_merged_data_model(self, scenarios: dict[str, ValidationResources]) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        assert resources.merged_data_model is not None
        assert resources.merged_data_model.views is not None
        assert len(resources.merged_data_model.views) > 0

    def test_merged_data_model_space(self, scenarios: dict[str, ValidationResources]) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        assert resources.merged_data_model.space == "my_space"


class TestValidationResourcesLimits:
    def test_limits_accessible(self, scenarios: dict[str, ValidationResources]) -> None:
        resources = scenarios["bi-directional-with-cdm"]
        assert resources.limits is not None
