from typing import cast

import networkx as nx
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
        "uncategorized_validators-additive": catalog.load_scenario(
            "uncategorized_validators",
            cdf_scenario_name="for_validators",
            modus_operandi="additive",
            include_cdm=True,
            format="validation-resource",
        ),
        "uncategorized_validators-rebuild": catalog.load_scenario(
            "uncategorized_validators",
            cdf_scenario_name="for_validators",
            modus_operandi="rebuild",
            include_cdm=True,
            format="validation-resource",
        ),
        "requires-constraints": catalog.load_scenario(
            "requires_constraints",
            cdf_scenario_name="for_validators",
            modus_operandi="additive",
            include_cdm=False,
            format="validation-resource",
        ),
    }
    return scenarios


class TestValidationResources:
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
                "uncategorized_validators-additive",
                ViewReference(space="my_space", external_id="ImplementationChain1", version="v1"),
                [
                    ViewReference(type="view", space="another_space", external_id="ImplementationChain2", version="v1"),
                    ViewReference(type="view", space="my_space", external_id="ImplementationChain3", version="v1"),
                    ViewReference(type="view", space="my_space", external_id="ImplementationChain4", version="v1"),
                ],
                id="view with implements has ancestors",
            ),
            pytest.param(
                "uncategorized_validators-rebuild",
                ViewReference(space="my_space", external_id="ImplementationChain1", version="v1"),
                [
                    ViewReference(type="view", space="another_space", external_id="ImplementationChain2", version="v1"),
                    ViewReference(type="view", space="my_space", external_id="ImplementationChain3", version="v1"),
                    ViewReference(type="view", space="my_space", external_id="ImplementationChain4", version="v1"),
                ],
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
        "scenario,view_ref,expected_properties",
        [
            pytest.param(
                "uncategorized_validators-additive",
                ViewReference(space="my_space", external_id="ImplementationChain1", version="v1"),
                [
                    ViewCorePropertyRequest(
                        connection_type="primary_property",
                        name="name1",
                        description="name1",
                        container=ContainerReference(
                            type="container", space="cdf_cdm", external_id="CogniteDescribable"
                        ),
                        containerPropertyIdentifier="name",
                        source=None,
                    ),
                    ViewCorePropertyRequest(
                        connection_type="primary_property",
                        name="name5",
                        description="name5",
                        container=ContainerReference(
                            type="container", space="nospace", external_id="ExistingContainer"
                        ),
                        containerPropertyIdentifier="name",
                        source=None,
                    ),
                    ViewCorePropertyRequest(
                        connection_type="primary_property",
                        name="name4",
                        description="name4",
                        container=ContainerReference(
                            type="container", space="cdf_cdm", external_id="CogniteDescribable"
                        ),
                        containerPropertyIdentifier="name",
                        source=None,
                    ),
                    ViewCorePropertyRequest(
                        connection_type="primary_property",
                        name="name3",
                        description="name3",
                        container=ContainerReference(
                            type="container", space="nospace", external_id="ExistingContainer"
                        ),
                        containerPropertyIdentifier="name",
                        source=None,
                    ),
                    ViewCorePropertyRequest(
                        connection_type="primary_property",
                        name="name2",
                        description="name2",
                        container=ContainerReference(
                            type="container", space="cdf_cdm", external_id="CogniteDescribable"
                        ),
                        containerPropertyIdentifier="name",
                        source=None,
                    ),
                ],
                id="Additive mode which bring in additional view property from CDF",
            ),
            pytest.param(
                "uncategorized_validators-rebuild",
                ViewReference(space="my_space", external_id="ImplementationChain1", version="v1"),
                [
                    ViewCorePropertyRequest(
                        connection_type="primary_property",
                        name="name1",
                        description="name1",
                        container=ContainerReference(
                            type="container", space="cdf_cdm", external_id="CogniteDescribable"
                        ),
                        containerPropertyIdentifier="name",
                        source=None,
                    ),
                    ViewCorePropertyRequest(
                        connection_type="primary_property",
                        name="name4",
                        description="name4",
                        container=ContainerReference(
                            type="container", space="cdf_cdm", external_id="CogniteDescribable"
                        ),
                        containerPropertyIdentifier="name",
                        source=None,
                    ),
                    ViewCorePropertyRequest(
                        connection_type="primary_property",
                        name="name3",
                        description="name3",
                        container=ContainerReference(
                            type="container", space="nospace", external_id="ExistingContainer"
                        ),
                        containerPropertyIdentifier="name",
                        source=None,
                    ),
                    ViewCorePropertyRequest(
                        connection_type="primary_property",
                        name="name2",
                        description="name2",
                        container=ContainerReference(
                            type="container", space="cdf_cdm", external_id="CogniteDescribable"
                        ),
                        containerPropertyIdentifier="name",
                        source=None,
                    ),
                ],
                id="Rebuild mode which should have one less property since view from CDF is not included",
            ),
        ],
    )
    def test_expand_view(
        self,
        scenario: str,
        view_ref: ViewReference,
        expected_properties: list[ViewCorePropertyRequest],
        scenarios: dict[str, ValidationResources],
    ) -> None:
        """This test is doing very complicated PING-PONG of implements and corresponding property inheritance.

        my_space:ImplementationChain1 -> another_space:ImplementationChain2 ->
        my_space:ImplementationChain3 -> my_space:ImplementationChain4

        where my_space is schema space, and another_space is external space, also
        re the first three views exist both locally and in CDF, where as the last only exist in CDF.

        By doing this, if we run `rebuild` mode, last view is not considered since it should be deleted in CDF
        after push of local schema to CDF, and thus properties from that view should not be inherited.

        This test also verifies that property definition are properly overridden, specifically property
        `name` which container mapping gets to be updated at each view in the chain, despite the property
        being implemented from the deepest view in the chain (ImplementationChain4 for additive and
        ImplementationChain3 for rebuild).
        """
        resources = scenarios[scenario]
        expanded_view = resources._expand_view(view_ref)
        expanded_view_from_cache = resources.expand_view_properties(view_ref)

        assert expanded_view
        assert expanded_view_from_cache
        assert expanded_view == expanded_view_from_cache
        assert expanded_view.properties
        assert expanded_view_from_cache.properties
        assert list(expanded_view.properties.values()) == expected_properties

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
        expanded_view = resources.expand_view_properties(view_ref)
        assert expanded_view
        assert len(expanded_view.properties) == expected_property_count

    def test_properties_by_view_inherits_from_ancestors(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that properties_by_view includes inherited properties from ancestors"""
        resources = scenarios["bi-directional-with-cdm"]
        descendant_ref = ViewReference(space="my_space", external_id="DescendantView", version="v1")
        ancestor_ref = ViewReference(space="my_space", external_id="AncestorView", version="v1")

        # Get ancestor's properties
        ancestor_expanded = cast(ViewRequest, resources.expand_view_properties(ancestor_ref))
        descendant_expanded = cast(ViewRequest, resources.expand_view_properties(descendant_ref))

        assert set(ancestor_expanded.properties.keys()).issubset(set(descendant_expanded.properties.keys())), (
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


class TestValidationResourcesRequiresConstraints:
    """Tests for requires constraint related methods in ValidationResources."""

    def test_container_to_views_basic(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test container_to_views returns correct view mappings."""
        resources = scenarios["requires-constraints"]
        container_to_views = resources.container_to_views

        # TransitiveMiddle appears in TransitiveView
        transitive_middle = ContainerReference(space="my_space", external_id="TransitiveMiddle")
        assert transitive_middle in container_to_views
        transitive_views = container_to_views[transitive_middle]
        assert any(v.external_id == "TransitiveView" for v in transitive_views)

    def test_view_to_containers_basic(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test view_to_containers returns correct container mappings."""
        resources = scenarios["requires-constraints"]
        view_to_containers = resources.view_to_containers

        # TransitiveView maps to TransitiveParent, TransitiveMiddle, TransitiveLeaf
        transitive_view = ViewReference(space="my_space", external_id="TransitiveView", version="v1")
        assert transitive_view in view_to_containers
        containers = view_to_containers[transitive_view]
        container_ids = {c.external_id for c in containers}
        assert container_ids == {"TransitiveParent", "TransitiveMiddle", "TransitiveLeaf"}

    def test_find_views_with_both_containers_found(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test containers that appear together in a view."""
        resources = scenarios["requires-constraints"]

        # AssetContainer and DescribableContainer appear together in AlwaysTogetherView
        asset = ContainerReference(space="my_space", external_id="AssetContainer")
        describable = ContainerReference(space="my_space", external_id="DescribableContainer")
        shared_views = resources.find_views_with_both_containers(asset, describable)
        assert len(shared_views) > 0

    def test_find_views_with_both_containers_not_found(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test containers that never appear together."""
        resources = scenarios["requires-constraints"]

        # OrderContainer and CustomerContainer never appear together
        order = ContainerReference(space="my_space", external_id="OrderContainer")
        customer = ContainerReference(space="my_space", external_id="CustomerContainer")
        shared_views = resources.find_views_with_both_containers(order, customer)
        assert len(shared_views) == 0

    def test_requires_graph_direct_successors(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test getting direct requires via graph successors."""
        resources = scenarios["requires-constraints"]

        # TransitiveMiddle directly requires TransitiveLeaf
        transitive_middle = ContainerReference(space="my_space", external_id="TransitiveMiddle")
        direct = set(resources.requires_graph.successors(transitive_middle))
        assert len(direct) == 1
        direct_ids = {c.external_id for c in direct}
        assert "TransitiveLeaf" in direct_ids

        # TransitiveLeaf has no requires
        transitive_leaf = ContainerReference(space="my_space", external_id="TransitiveLeaf")
        direct = set(resources.requires_graph.successors(transitive_leaf))
        assert len(direct) == 0

    def test_requires_graph_descendants(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test getting transitive requires via nx.descendants (including indirect)."""
        import networkx as nx

        resources = scenarios["requires-constraints"]

        # CycleContainerA requires CycleContainerB which requires CycleContainerA (cycle)
        cycle_a = ContainerReference(space="my_space", external_id="CycleContainerA")
        transitive = nx.descendants(resources.requires_graph, cycle_a)
        transitive_ids = {c.external_id for c in transitive}
        # Should handle cycle and return both
        assert "CycleContainerB" in transitive_ids

    def test_requires_graph_descendants_excludes_self(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that nx.descendants doesn't include the container itself (except in cycles)."""
        import networkx as nx

        resources = scenarios["requires-constraints"]

        transitive_middle = ContainerReference(space="my_space", external_id="TransitiveMiddle")
        transitive = nx.descendants(resources.requires_graph, transitive_middle)
        transitive_ids = {c.external_id for c in transitive}
        assert "TransitiveMiddle" not in transitive_ids
        assert "TransitiveLeaf" in transitive_ids

    def test_requires_graph_structure(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that requires_graph is built correctly."""
        resources = scenarios["requires-constraints"]
        graph = resources.requires_graph

        # Check edges exist
        transitive_middle = ContainerReference(space="my_space", external_id="TransitiveMiddle")
        transitive_leaf = ContainerReference(space="my_space", external_id="TransitiveLeaf")
        assert graph.has_edge(transitive_middle, transitive_leaf)

        # Check cycle edges
        cycle_a = ContainerReference(space="my_space", external_id="CycleContainerA")
        cycle_b = ContainerReference(space="my_space", external_id="CycleContainerB")
        assert graph.has_edge(cycle_a, cycle_b)
        assert graph.has_edge(cycle_b, cycle_a)

    def test_requires_constraint_cycles(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test cycle detection in requires constraints."""
        resources = scenarios["requires-constraints"]
        cycles = resources.requires_constraint_cycles

        # Should detect the CycleContainerA <-> CycleContainerB cycle
        assert len(cycles) > 0
        cycle_ids = {c.external_id for cycle in cycles for c in cycle}
        assert "CycleContainerA" in cycle_ids
        assert "CycleContainerB" in cycle_ids

        # Linear chain should not be detected as a cycle
        assert "TransitiveMiddle" not in cycle_ids
        assert "TransitiveLeaf" not in cycle_ids

    def test_has_full_requires_hierarchy_true(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test view with complete requires hierarchy."""
        resources = scenarios["requires-constraints"]

        # TagView has TagContainer, TagAssetContainer, TagDescribableContainer
        # TagAssetContainer requires TagDescribableContainer
        # If TagContainer required TagAssetContainer, it would be complete
        # But it doesn't, so we check TransitiveView instead with modified expectations
        # TransitiveView: Parent, Middle, Leaf - Middle requires Leaf
        # Not complete since Parent doesn't require Middle
        transitive_view = ViewReference(space="my_space", external_id="TransitiveView", version="v1")
        containers = resources.view_to_containers.get(transitive_view, set())
        # This should be False since TransitiveParent doesn't require TransitiveMiddle
        assert not resources.has_full_requires_hierarchy(containers)

    def test_has_full_requires_hierarchy_single_container(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test view with single container always has full hierarchy."""
        resources = scenarios["requires-constraints"]

        # OrderOnlyView has only OrderContainer
        order_view = ViewReference(space="my_space", external_id="OrderOnlyView", version="v1")
        containers = resources.view_to_containers.get(order_view, set())
        assert len(containers) == 1
        assert resources.has_full_requires_hierarchy(containers)

    def test_optimal_requires_tree_cached(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that optimal_requires_tree is computed and cached."""
        resources = scenarios["requires-constraints"]

        # Access the property twice - should be the same object (cached)
        tree1 = resources.optimal_requires_tree
        tree2 = resources.optimal_requires_tree
        assert tree1 is tree2

    def test_get_missing_requires_for_view_no_missing(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test get_missing_requires_for_view when hierarchy is already complete."""
        resources = scenarios["requires-constraints"]

        # TagView has TagAssetContainer requiring TagDescribableContainer
        # If we only include those two, hierarchy is complete
        tag_asset = ContainerReference(space="my_space", external_id="TagAssetContainer")
        tag_describable = ContainerReference(space="my_space", external_id="TagDescribableContainer")

        missing = resources.get_missing_requires_for_view({tag_asset, tag_describable})
        # TagAssetContainer already requires TagDescribableContainer, so no missing
        assert len(missing) == 0

    def test_get_missing_requires_for_view_simple_case(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test get_missing_requires_for_view for containers with no existing requires."""
        resources = scenarios["requires-constraints"]

        # AssetContainer and DescribableContainer have no requires between them
        asset = ContainerReference(space="my_space", external_id="AssetContainer")
        describable = ContainerReference(space="my_space", external_id="DescribableContainer")

        missing = resources.get_missing_requires_for_view({asset, describable})
        # Should recommend one constraint to connect them
        assert len(missing) == 1
        # The edge should connect the two containers
        src, dst = missing[0]
        assert {src.external_id, dst.external_id} == {"AssetContainer", "DescribableContainer"}

    def test_get_missing_requires_for_view_transitive_case(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test get_missing_requires_for_view leverages existing transitivity."""
        resources = scenarios["requires-constraints"]

        # TransitiveView: Parent, Middle, Leaf
        # Middle already requires Leaf
        # Should recommend Parent→Middle (not Parent→Leaf, as that would be redundant)
        parent = ContainerReference(space="my_space", external_id="TransitiveParent")
        middle = ContainerReference(space="my_space", external_id="TransitiveMiddle")
        leaf = ContainerReference(space="my_space", external_id="TransitiveLeaf")

        missing = resources.get_missing_requires_for_view({parent, middle, leaf})

        # Should have 1 missing edge: Parent→Middle (Leaf is covered transitively)
        assert len(missing) == 1
        src, dst = missing[0]
        # Parent should require Middle (which already requires Leaf)
        assert src.external_id == "TransitiveParent"
        assert dst.external_id == "TransitiveMiddle"

    def test_get_missing_requires_for_view_single_container(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test get_missing_requires_for_view with single container returns empty."""
        resources = scenarios["requires-constraints"]

        asset = ContainerReference(space="my_space", external_id="AssetContainer")
        missing = resources.get_missing_requires_for_view({asset})
        assert missing == []

    def test_optimal_requires_tree_consistency(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that optimal_requires_tree gives consistent recommendations across views."""
        resources = scenarios["requires-constraints"]

        # Get the global tree
        global_tree = resources.optimal_requires_tree

        # For any container pair in the tree, the recommendation should be consistent
        # regardless of which view we're looking at
        for src, dst in global_tree:
            # The edge direction should always be the same
            reverse_edge = (dst, src)
            assert reverse_edge not in global_tree, f"Tree contains both {src}->{dst} and {dst}->{src}"

    def test_optimal_requires_tree_no_cdf_sources(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that CDF built-in containers are never recommended as sources."""
        from cognite.neat._data_model._constants import CDF_BUILTIN_SPACES

        resources = scenarios["requires-constraints"]
        global_tree = resources.optimal_requires_tree

        for src, dst in global_tree:
            assert src.space not in CDF_BUILTIN_SPACES, (
                f"CDF built-in container '{src}' should not be recommended as source"
            )

    def test_get_missing_requires_for_view_no_cdf_sources(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that per-view recommendations never have CDF built-in containers as sources."""
        from cognite.neat._data_model._constants import CDF_BUILTIN_SPACES

        resources = scenarios["requires-constraints"]

        # Test with a view that has multiple containers
        asset = ContainerReference(space="my_space", external_id="AssetContainer")
        describable = ContainerReference(space="my_space", external_id="DescribableContainer")

        missing = resources.get_missing_requires_for_view({asset, describable})

        for src, dst in missing:
            assert src.space not in CDF_BUILTIN_SPACES, (
                f"CDF built-in container '{src}' should not be recommended as source"
            )

    def test_missing_requires_includes_external_container_recommendations(
        self, scenarios: dict[str, ValidationResources]
    ) -> None:
        """Test recommendations include edges to containers outside the current view.

        Scenario (mimics real FunctionalLocation/Tag/CogniteAsset pattern):
        - FuncLocView: [FuncLocContainer, FuncLocTagContainer, FuncLocDescribableContainer]
        - FuncLocTagView: [FuncLocTagContainer, FuncLocAssetContainer, FuncLocDescribableContainer]
        - FuncLocAssetContainer requires FuncLocDescribableContainer

        Key: FuncLocTagContainer ONLY appears with FuncLocAssetContainer (no reduced view).
        This forces the MST to recommend FuncLocTagContainer → FuncLocAssetContainer.

        Expected recommendations for FuncLocView:
        - FuncLocContainer → FuncLocTagContainer (local edge within view)
        - FuncLocTagContainer → FuncLocAssetContainer (MST recommendation, even though
          FuncLocAssetContainer is not in FuncLocView - it provides transitive coverage)
        """
        resources = scenarios["requires-constraints"]

        func_loc = ContainerReference(space="my_space", external_id="FuncLocContainer")
        tag = ContainerReference(space="my_space", external_id="FuncLocTagContainer")
        asset = ContainerReference(space="my_space", external_id="FuncLocAssetContainer")
        describable = ContainerReference(space="my_space", external_id="FuncLocDescribableContainer")

        missing = resources.get_missing_requires_for_view({func_loc, tag, describable})

        # Should have recommendations
        assert len(missing) > 0, "Expected recommendations for FuncLocView"

        # Should include an edge connecting FuncLocContainer to the hierarchy
        func_loc_edges = [(src, dst) for src, dst in missing if func_loc in (src, dst)]
        assert len(func_loc_edges) > 0, f"Expected edge connecting FuncLocContainer, got: {missing}"

        # Should include FuncLocTagContainer → FuncLocAssetContainer even though
        # FuncLocAssetContainer is not in this view - it provides transitive coverage to Describable
        tag_to_asset = (tag, asset)
        assert tag_to_asset in missing, (
            f"Expected FuncLocTagContainer → FuncLocAssetContainer (external recommendation), got: {missing}"
        )

    def test_bridge_with_suboptimal_requires(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test recommendations when intermediate container has suboptimal requires.

        Scenario (mimics Tag requiring CogniteSourceable instead of CogniteAsset):
        - BridgeTagContainer requires BridgeSourceableContainer (suboptimal)
        - BridgeAssetContainer requires BridgeSourceableContainer AND BridgeDescribableContainer
        - BridgeCompressorContainer requires BridgeTagContainer
        - BridgeCompressorView: [BridgeCompressorContainer, BridgeTagContainer, BridgeDescribableContainer]

        Expected: BridgeTagContainer → BridgeAssetContainer should be recommended
        (provides transitive coverage of Describable via Asset, not direct Tag→Describable)
        """
        resources = scenarios["requires-constraints"]

        compressor = ContainerReference(space="my_space", external_id="BridgeCompressorContainer")
        tag = ContainerReference(space="my_space", external_id="BridgeTagContainer")
        asset = ContainerReference(space="my_space", external_id="BridgeAssetContainer")
        describable = ContainerReference(space="my_space", external_id="BridgeDescribableContainer")

        missing = resources.get_missing_requires_for_view({compressor, tag, describable})

        # Should recommend Tag → Asset (better coverage) rather than Compressor → Describable
        tag_to_asset = (tag, asset)
        compressor_to_describable = (compressor, describable)

        assert tag_to_asset in missing, (
            f"Expected BridgeTagContainer → BridgeAssetContainer (bridge recommendation), got: {missing}"
        )
        assert compressor_to_describable not in missing, (
            f"Should NOT recommend Compressor → Describable (suboptimal), got: {missing}"
        )

    def test_no_cross_equipment_recommendations(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that we don't recommend constraints between unrelated equipment containers.

        Scenario: Multiple equipment views (Compressor, EquipmentB, EquipmentC) all map to
        their specific container + Tag + Describable. They should NOT get recommendations
        like Tag → EquipmentB for the EquipmentC view.

        The MST should recognize that these equipment containers never appear together
        and should not create cross-dependencies.
        """
        resources = scenarios["requires-constraints"]

        # Get containers
        compressor = ContainerReference(space="my_space", external_id="BridgeCompressorContainer")
        equipment_b = ContainerReference(space="my_space", external_id="BridgeEquipmentBContainer")
        equipment_c = ContainerReference(space="my_space", external_id="BridgeEquipmentCContainer")
        tag = ContainerReference(space="my_space", external_id="BridgeTagContainer")
        describable = ContainerReference(space="my_space", external_id="BridgeDescribableContainer")

        # Check recommendations for EquipmentCView
        equipment_c_view_containers = {equipment_c, tag, describable}
        missing = resources.get_missing_requires_for_view(equipment_c_view_containers)

        # Should NOT recommend cross-equipment edges
        for src, dst in missing:
            # Tag should not require any equipment container other than potentially through Asset
            if src.external_id == "BridgeTagContainer":
                assert dst.external_id not in ["BridgeEquipmentBContainer", "BridgeCompressorContainer"], (
                    f"Should NOT recommend Tag → {dst.external_id} (unrelated equipment)"
                )
            # Equipment containers should not require other equipment containers
            if src.external_id in ["BridgeEquipmentBContainer", "BridgeCompressorContainer"]:
                assert dst.external_id not in ["BridgeEquipmentCContainer"], (
                    f"Should NOT recommend {src.external_id} → EquipmentC (unrelated equipment)"
                )

    def test_no_cycle_recommendations(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that we don't recommend constraints that would create cycles.

        Scenario: BridgeCompressorContainer already requires BridgeTagContainer.
        We should NOT recommend BridgeTagContainer → BridgeCompressorContainer.
        """
        resources = scenarios["requires-constraints"]

        compressor = ContainerReference(space="my_space", external_id="BridgeCompressorContainer")
        tag = ContainerReference(space="my_space", external_id="BridgeTagContainer")
        describable = ContainerReference(space="my_space", external_id="BridgeDescribableContainer")

        # BridgeCompressorContainer requires BridgeTagContainer (in test data)
        # Verify this constraint exists
        assert compressor in resources.requires_graph
        assert tag in nx.descendants(resources.requires_graph, compressor)

        # Get recommendations for a view with these containers
        missing = resources.get_missing_requires_for_view({compressor, tag, describable})

        # Should NOT recommend Tag → Compressor (would create cycle)
        tag_to_compressor = (tag, compressor)
        assert tag_to_compressor not in missing, (
            f"Should NOT recommend Tag → Compressor (would create cycle with existing Compressor → Tag), got: {missing}"
        )

    def test_conflicting_containers_with_disjoint_siblings(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test detection of containers that appear with different siblings in different views.

        Scenario: SharedConflictContainer appears in:
        - ConflictFileView: SharedConflictContainer + ConflictFileContainer
        - ConflictTimeSeriesView: SharedConflictContainer + ConflictTimeSeriesContainer

        If SharedConflictContainer requires ConflictFileContainer, ConflictTimeSeriesView ingestion breaks.
        If SharedConflictContainer requires ConflictTimeSeriesContainer, ConflictFileView ingestion breaks.
        This is an unsolvable conflict and should be detected.
        """
        resources = scenarios["requires-constraints"]

        # Find conflicting containers
        conflicting = resources.conflicting_containers

        # SharedConflictContainer should be detected as conflicting
        shared_ref = ContainerReference(space="my_space", external_id="SharedConflictContainer")
        assert shared_ref in conflicting, (
            f"Expected SharedConflictContainer to be detected as conflicting "
            f"(disjoint siblings ConflictFileContainer and ConflictTimeSeriesContainer), "
            f"got: {conflicting}"
        )

    def test_outer_containers_not_marked_as_conflicting(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that containers are NOT marked as conflicting when siblings are 'outer' containers.

        Scenario: BridgeTagContainer appears in multiple views:
        - BridgeTagView: BridgeTagContainer + BridgeAssetContainer + BridgeDescribableContainer
        - BridgeCompressorView: BridgeCompressorContainer + BridgeTagContainer + BridgeDescribableContainer
        - EquipmentBView: EquipmentBContainer + BridgeTagContainer + BridgeDescribableContainer

        BridgeCompressorContainer and EquipmentBContainer are unique across views, but they are
        'outer' containers that REQUIRE BridgeTagContainer (not candidates for Tag to require).
        This should NOT be marked as a conflict - Tag → Asset is a valid recommendation.
        """
        resources = scenarios["requires-constraints"]

        # Find conflicting containers
        conflicting = resources.conflicting_containers

        # BridgeTagContainer should NOT be marked as conflicting
        tag_ref = ContainerReference(space="my_space", external_id="BridgeTagContainer")
        assert tag_ref not in conflicting, (
            f"BridgeTagContainer should NOT be marked as conflicting - "
            f"outer containers (Compressor, EquipmentB) require Tag, not vice versa. "
            f"Tag → Asset is a valid recommendation. Got conflicting: {conflicting}"
        )
