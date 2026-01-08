from typing import cast

import networkx as nx
import pytest
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat._data_model._analysis import ResourceSource, ValidationResources
from cognite.neat._data_model._constants import CDF_BUILTIN_SPACES
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

    @pytest.mark.parametrize(
        "container_ids,expect_found",
        [
            pytest.param(
                ["AssetContainer", "DescribableContainer"],
                True,
                id="containers-appear-together",
            ),
            pytest.param(
                ["OrderContainer", "CustomerContainer"],
                False,
                id="containers-never-together",
            ),
        ],
    )
    def test_find_views_mapping_to_containers(
        self,
        container_ids: list[str],
        expect_found: bool,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        """Test find_views_mapping_to_containers for various container combinations."""
        resources = scenarios["requires-constraints"]
        containers = [ContainerReference(space="my_space", external_id=cid) for cid in container_ids]
        shared_views = resources.find_views_mapping_to_containers(containers)

        if expect_found:
            assert len(shared_views) > 0, f"Expected shared views for {container_ids}"
        else:
            assert len(shared_views) == 0, f"Expected no shared views for {container_ids}"

    @pytest.mark.parametrize(
        "container_id,expected_successors",
        [
            pytest.param(
                "TransitiveMiddle",
                ["TransitiveLeaf"],
                id="has-direct-requires",
            ),
            pytest.param(
                "TransitiveLeaf",
                [],
                id="no-requires",
            ),
        ],
    )
    def test_requires_graph_direct_successors(
        self,
        container_id: str,
        expected_successors: list[str],
        scenarios: dict[str, ValidationResources],
    ) -> None:
        """Test getting direct requires via graph successors."""
        resources = scenarios["requires-constraints"]
        container = ContainerReference(space="my_space", external_id=container_id)
        direct = set(resources.requires_graph.successors(container))
        direct_ids = {c.external_id for c in direct}

        assert direct_ids == set(expected_successors), (
            f"{container_id} successors: expected {expected_successors}, got {direct_ids}"
        )

    @pytest.mark.parametrize(
        "container_id,expected_in,expected_not_in",
        [
            pytest.param(
                "CycleContainerA",
                ["CycleContainerB"],
                [],
                id="handles-cycles",
            ),
            pytest.param(
                "TransitiveMiddle",
                ["TransitiveLeaf"],
                ["TransitiveMiddle"],
                id="excludes-self-includes-descendants",
            ),
        ],
    )
    def test_requires_graph_descendants(
        self,
        container_id: str,
        expected_in: list[str],
        expected_not_in: list[str],
        scenarios: dict[str, ValidationResources],
    ) -> None:
        """Test nx.descendants on requires_graph for various scenarios."""
        resources = scenarios["requires-constraints"]
        container = ContainerReference(space="my_space", external_id=container_id)
        descendants = nx.descendants(resources.requires_graph, container)
        descendant_ids = {c.external_id for c in descendants}

        for expected in expected_in:
            assert expected in descendant_ids, f"{expected} should be in descendants of {container_id}"
        for not_expected in expected_not_in:
            assert not_expected not in descendant_ids, f"{not_expected} should NOT be in descendants of {container_id}"

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

    @pytest.mark.parametrize(
        "view_id,expected_complete",
        [
            pytest.param(
                "TransitiveView",
                False,
                id="incomplete-hierarchy",
            ),
            pytest.param(
                "OrderOnlyView",
                True,
                id="single-container-always-complete",
            ),
        ],
    )
    def test_has_full_requires_hierarchy(
        self,
        view_id: str,
        expected_complete: bool,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        """Test has_full_requires_hierarchy for various view scenarios."""
        resources = scenarios["requires-constraints"]
        view_ref = ViewReference(space="my_space", external_id=view_id, version="v1")
        containers = resources.view_to_containers.get(view_ref, set())

        result = resources.has_full_requires_hierarchy(containers)
        assert result == expected_complete, f"View {view_id}: expected {expected_complete}, got {result}"

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

    def test_get_missing_requires_for_view_updates_coverage_correctly(
        self, scenarios: dict[str, ValidationResources]
    ) -> None:
        """Test that coverage is updated correctly as edges are added.

        This tests that 'uncovered' is not stale when checking subsequent MST edges.
        If the first edge covers a container, subsequent checks should see updated coverage.
        """
        resources = scenarios["requires-constraints"]

        # BridgeSiblingAView: SiblingA, Tag, Describable
        # BridgeTagView also exists: Tag, Asset, Describable
        # MST should recommend Tag→Asset for Tag view
        # For SiblingA view, if Tag→Asset is in MST, after adding it,
        # coverage should update so we don't add redundant edges
        sibling_a = ContainerReference(space="my_space", external_id="BridgeSiblingAContainer")
        tag = ContainerReference(space="my_space", external_id="BridgeTagContainer")
        describable = ContainerReference(space="my_space", external_id="BridgeDescribableContainer")

        missing = resources.get_missing_requires_for_view({sibling_a, tag, describable})

        # Count edges - should not have redundant recommendations
        # Each container pair should only have ONE edge connecting them (directly or transitively)
        sources = [src for src, dst in missing]
        for src in sources:
            src_edges = [(s, d) for s, d in missing if s == src]
            # A source shouldn't need multiple edges if one provides transitive coverage
            # This is a soft check - the pruning step should handle redundancy
            assert len(src_edges) <= 2, f"Source {src} has too many edges: {src_edges}"

    def test_get_missing_requires_for_view_single_container(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test get_missing_requires_for_view with single container returns empty."""
        resources = scenarios["requires-constraints"]

        asset = ContainerReference(space="my_space", external_id="AssetContainer")
        missing = resources.get_missing_requires_for_view({asset})
        assert len(missing) == 0

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

    def test_get_missing_requires_never_recommends_cdf_sources(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that get_missing_requires_for_view never recommends CDF containers as sources."""
        resources = scenarios["requires-constraints"]

        # Check all views - none should have CDF sources in recommendations
        for view_ref in resources.merged.views:
            containers = resources.view_to_containers.get(view_ref, set())
            if len(containers) < 2:
                continue

            missing = resources.get_missing_requires_for_view(containers)
            for src, _ in missing:
                assert src.space not in CDF_BUILTIN_SPACES, (
                    f"View {view_ref}: CDF container '{src}' should not be recommended as source"
                )

    @pytest.mark.parametrize(
        "path_from,path_to,error_desc",
        [
            pytest.param("src", "dst", "path already exists", id="no-transitive-redundancy"),
            pytest.param("dst", "src", "would form cycle", id="no-cycle-forming-edges"),
        ],
    )
    def test_optimal_requires_tree_no_invalid_paths(
        self,
        path_from: str,
        path_to: str,
        error_desc: str,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        """Test that optimal_requires_tree edges don't have invalid paths."""
        resources = scenarios["requires-constraints"]

        for src, dst in resources.optimal_requires_tree:
            from_node = src if path_from == "src" else dst
            to_node = dst if path_to == "dst" else src
            assert not nx.has_path(resources.requires_graph, from_node, to_node), f"Edge {src} → {dst}: {error_desc}"

    def test_optimal_requires_tree_empty_when_complete(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that optimal_requires_tree returns empty when all hierarchies are complete.

        If every pair of containers that appear together in a view is already connected
        (directly or transitively), there's nothing to recommend.
        """
        resources = scenarios["requires-constraints"]
        global_tree = resources.optimal_requires_tree

        # For the tree to be non-empty, there must be container pairs in views
        # that are NOT connected in the requires_graph
        # This test verifies the property: if tree is empty, all pairs are connected
        if not global_tree:
            # Verify all pairs in views are connected
            for view_ref in resources.merged.views:
                containers = resources.view_to_containers.get(view_ref, set())
                for c1 in containers:
                    for c2 in containers:
                        if c1 != c2:
                            connected = nx.has_path(resources.requires_graph, c1, c2) or nx.has_path(
                                resources.requires_graph, c2, c1
                            )
                            assert connected, f"Tree is empty but {c1} and {c2} are not connected"

    def test_optimal_requires_tree_handles_disconnected_components(
        self, scenarios: dict[str, ValidationResources]
    ) -> None:
        """Test that optimal_requires_tree handles disconnected container groups.

        Scenario: Two groups of containers that never appear together in any view.
        - Group A: DisconnectedGroupAContainer1, DisconnectedGroupAContainer2 (in DisconnectedGroupAView)
        - Group B: DisconnectedGroupBContainer1, DisconnectedGroupBContainer2 (in DisconnectedGroupBView)

        The MST should produce recommendations for both groups independently.
        """
        resources = scenarios["requires-constraints"]
        global_tree = resources.optimal_requires_tree

        # Define the containers
        group_a1 = ContainerReference(space="my_space", external_id="DisconnectedGroupAContainer1")
        group_a2 = ContainerReference(space="my_space", external_id="DisconnectedGroupAContainer2")
        group_b1 = ContainerReference(space="my_space", external_id="DisconnectedGroupBContainer1")
        group_b2 = ContainerReference(space="my_space", external_id="DisconnectedGroupBContainer2")

        # Get edges involving each group
        group_a_edges = [(src, dst) for src, dst in global_tree if {src, dst} & {group_a1, group_a2}]
        group_b_edges = [(src, dst) for src, dst in global_tree if {src, dst} & {group_b1, group_b2}]

        # Both groups should have at least one edge (to connect their containers)
        assert len(group_a_edges) >= 1, f"Expected edge for Group A, got: {group_a_edges}"
        assert len(group_b_edges) >= 1, f"Expected edge for Group B, got: {group_b_edges}"

        # No edge should cross between groups (they never appear together)
        for src, dst in global_tree:
            group_a_containers = {group_a1, group_a2}
            group_b_containers = {group_b1, group_b2}
            src_in_a = src in group_a_containers
            dst_in_b = dst in group_b_containers
            src_in_b = src in group_b_containers
            dst_in_a = dst in group_a_containers
            assert not (src_in_a and dst_in_b), f"Cross-group edge {src} → {dst}"
            assert not (src_in_b and dst_in_a), f"Cross-group edge {src} → {dst}"

    def test_get_missing_requires_for_view_no_cdf_sources(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that per-view recommendations never have CDF built-in containers as sources."""
        from cognite.neat._data_model._constants import CDF_BUILTIN_SPACES

        resources = scenarios["requires-constraints"]

        # Test with a view that has multiple containers
        asset = ContainerReference(space="my_space", external_id="AssetContainer")
        describable = ContainerReference(space="my_space", external_id="DescribableContainer")

        missing = resources.get_missing_requires_for_view({asset, describable})

        for src, _ in missing:
            assert src.space not in CDF_BUILTIN_SPACES, (
                f"CDF built-in container '{src}' should not be recommended as source"
            )

    @pytest.mark.parametrize(
        "view_container_ids,expected_in,expected_not_in",
        [
            pytest.param(
                ["FuncLocContainer", "FuncLocTagContainer", "FuncLocDescribableContainer"],
                [("FuncLocTagContainer", "FuncLocAssetContainer")],
                [],
                id="external-container-recommendations",
            ),
            pytest.param(
                ["BridgeSiblingAContainer", "BridgeTagContainer", "BridgeDescribableContainer"],
                [("BridgeTagContainer", "BridgeAssetContainer")],
                [("BridgeSiblingAContainer", "BridgeDescribableContainer")],
                id="bridge-prefers-better-coverage",
            ),
        ],
    )
    def test_get_missing_requires_edge_selection(
        self,
        view_container_ids: list[str],
        expected_in: list[tuple[str, str]],
        expected_not_in: list[tuple[str, str]],
        scenarios: dict[str, ValidationResources],
    ) -> None:
        """Test that get_missing_requires_for_view selects correct edges."""
        resources = scenarios["requires-constraints"]

        view_containers = {ContainerReference(space="my_space", external_id=cid) for cid in view_container_ids}
        missing = resources.get_missing_requires_for_view(view_containers)

        # Convert to comparable format
        missing_ids = {(src.external_id, dst.external_id) for src, dst in missing}

        for src_id, dst_id in expected_in:
            assert (src_id, dst_id) in missing_ids, (
                f"Expected {src_id} → {dst_id} in recommendations, got: {missing_ids}"
            )

        for src_id, dst_id in expected_not_in:
            assert (src_id, dst_id) not in missing_ids, f"Should NOT recommend {src_id} → {dst_id}, got: {missing_ids}"

    def test_no_cross_sibling_recommendations(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that we don't recommend constraints between unrelated sibling containers.

        Scenario: Multiple views share common containers (Tag, Describable) but have
        unique leaf containers (A, B, C) that never appear together.
        Recommendations should not create cross-dependencies between these siblings.
        """
        resources = scenarios["requires-constraints"]

        sibling_a = ContainerReference(space="my_space", external_id="BridgeSiblingAContainer")
        sibling_b = ContainerReference(space="my_space", external_id="BridgeSiblingBContainer")
        sibling_c = ContainerReference(space="my_space", external_id="BridgeSiblingCContainer")
        tag = ContainerReference(space="my_space", external_id="BridgeTagContainer")
        describable = ContainerReference(space="my_space", external_id="BridgeDescribableContainer")

        # Check recommendations for a view with sibling_c
        view_containers = {sibling_c, tag, describable}
        missing = resources.get_missing_requires_for_view(view_containers)

        # Siblings that never appear together should not have cross-dependencies
        unrelated_siblings = {sibling_a.external_id, sibling_b.external_id}
        for src, dst in missing:
            if src == tag:
                assert dst.external_id not in unrelated_siblings, (
                    f"Should NOT recommend Tag → {dst.external_id} (unrelated sibling)"
                )
            if src.external_id in unrelated_siblings:
                assert dst != sibling_c, f"Should NOT recommend {src.external_id} → sibling_c (unrelated)"

    def test_no_cycle_recommendations(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that we don't recommend constraints that would create cycles.

        Scenario: BridgeSiblingAContainer already requires BridgeTagContainer.
        We should NOT recommend BridgeTagContainer → BridgeSiblingAContainer.
        """
        resources = scenarios["requires-constraints"]

        sibling_a = ContainerReference(space="my_space", external_id="BridgeSiblingAContainer")
        tag = ContainerReference(space="my_space", external_id="BridgeTagContainer")
        describable = ContainerReference(space="my_space", external_id="BridgeDescribableContainer")

        # Verify the requires relationship exists (SiblingA → Tag)
        assert nx.has_path(resources.requires_graph, sibling_a, tag), "SiblingA should require Tag for this test"

        missing = resources.get_missing_requires_for_view({sibling_a, tag, describable})

        # Should NOT recommend Tag → SiblingA (would create cycle)
        tag_to_sibling_a = (tag, sibling_a)
        assert tag_to_sibling_a not in missing, (
            f"Should NOT recommend Tag → SiblingA (would create cycle with existing SiblingA → Tag), got: {missing}"
        )

    def test_cdf_source_edges_are_flipped_in_mst(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that CDF source edges are flipped to user source edges in optimal_requires_tree.

        With Step2CombinedView mapping to {UserA, UserB, CdfBridge}, the MST picks
        a user container as root and connects everything from there.
        No CDF containers should ever be sources in the MST.
        """
        resources = scenarios["requires-constraints"]

        mst_edges = set(resources.optimal_requires_tree)

        # No CDF source edges should exist (all are flipped to user sources)
        cdf_source_edges = [(src, dst) for src, dst in mst_edges if src.space == "cdf_cdm"]
        assert len(cdf_source_edges) == 0, f"Expected no CDF source edges, got: {cdf_source_edges}"

        # All edges should have user containers as sources
        for src, _ in mst_edges:
            assert src.space != "cdf_cdm", f"CDF container should not be source: {src}"

    def test_three_container_view_with_cdf_bridge(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test REAL view with 3 containers: UserA, UserB, and CDF bridge.

        Step2CombinedView maps to all three: {UserA, UserB, CdfBridge}
        The MST should create edges so that one user container is the root
        and can reach all other containers.

        Expected: A complete hierarchy with a user container as outermost.
        """
        resources = scenarios["requires-constraints"]

        user_a = ContainerReference(space="my_space", external_id="Step2UserAContainer")
        user_b = ContainerReference(space="my_space", external_id="Step2UserBContainer")
        cdf_bridge = ContainerReference(space="cdf_cdm", external_id="CdfBridgeContainer")

        # Use the REAL view that maps to all 3 containers
        combined_view = ViewReference(space="my_space", external_id="Step2CombinedView", version="1")
        view_containers = resources.view_to_containers.get(combined_view, set())

        assert view_containers == {user_a, user_b, cdf_bridge}, (
            f"Expected view to have all 3 containers, got: {view_containers}"
        )

        missing = resources.get_missing_requires_for_view(view_containers)
        missing_ids = {(src.external_id, dst.external_id) for src, dst in missing}

        # At minimum, we need edges to connect all 3 containers
        assert len(missing) >= 2, f"Expected at least 2 recommendations to connect 3 containers, got: {missing_ids}"

        # All sources should be user containers (no CDF sources)
        for src, _ in missing:
            assert src.space != "cdf_cdm", f"CDF container should not be source: {src}"

        # Verify hierarchy is complete after applying recommendations
        work_graph = resources.requires_graph.copy()
        for src, dst in missing:
            work_graph.add_edge(src, dst)

        # Check that some user container can reach all others
        user_containers = [c for c in view_containers if c.space != "cdf_cdm"]
        hierarchy_complete = any(
            all(c in nx.descendants(work_graph, u) | {u} for c in view_containers) for u in user_containers
        )
        assert hierarchy_complete, (
            f"Recommendations should create complete hierarchy. "
            f"Missing: {missing_ids}, Graph edges: {list(work_graph.edges())[:20]}"
        )

    @pytest.mark.parametrize(
        "container_id,expected_conflicting",
        [
            pytest.param(
                "SharedConflictContainer",
                True,
                id="disjoint-siblings-is-conflicting",
            ),
            pytest.param(
                "BridgeTagContainer",
                False,
                id="outer-containers-not-conflicting",
            ),
            pytest.param(
                "BridgeDescribableContainer",
                False,
                id="common-sibling-not-conflicting",
            ),
            pytest.param(
                "OrderContainer",
                False,
                id="single-view-not-conflicting",
            ),
        ],
    )
    def test_conflicting_containers(
        self,
        container_id: str,
        expected_conflicting: bool,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        """Test conflicting container detection for various scenarios."""
        resources = scenarios["requires-constraints"]
        conflicting = resources.conflicting_containers
        container_ref = ContainerReference(space="my_space", external_id=container_id)

        if expected_conflicting:
            assert container_ref in conflicting, f"{container_id} should be conflicting. Got: {conflicting}"
        else:
            assert container_ref not in conflicting, f"{container_id} should NOT be conflicting. Got: {conflicting}"

    @pytest.mark.parametrize(
        "src_id,dst_id,check_view_id,expected_in_affected",
        [
            pytest.param(
                "BridgeTagContainer",
                "BridgeAssetContainer",
                "BridgeTagView",
                False,
                id="dst-in-view-not-affected",
            ),
            pytest.param(
                "TagContainer",
                "TagDescribableContainer",
                "TagView",
                False,
                id="dst-transitively-covered-not-affected",
            ),
            pytest.param(
                "NonExistentContainer",
                "BridgeAssetContainer",
                None,
                None,  # Special case: expect empty set
                id="src-not-in-any-view-returns-empty",
            ),
        ],
    )
    def test_find_views_affected_by_requires(
        self,
        src_id: str,
        dst_id: str,
        check_view_id: str | None,
        expected_in_affected: bool | None,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        """Test find_views_affected_by_requires for various scenarios."""
        resources = scenarios["requires-constraints"]
        src = ContainerReference(space="my_space", external_id=src_id)
        dst = ContainerReference(space="my_space", external_id=dst_id)

        affected = resources.find_views_affected_by_requires(src, dst)

        if expected_in_affected is None:
            # Special case: expect empty set
            assert affected == set(), f"Expected empty set, got: {affected}"
        elif check_view_id:
            view_ref = ViewReference(space="my_space", external_id=check_view_id, version="v1")
            if expected_in_affected:
                assert view_ref in affected, f"{check_view_id} should be affected. Got: {affected}"
            else:
                assert view_ref not in affected, f"{check_view_id} should NOT be affected. Got: {affected}"

    def test_find_views_affected_exclude_view_parameter(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that the exclude_view parameter removes that view from affected results."""
        resources = scenarios["requires-constraints"]

        tag = ContainerReference(space="my_space", external_id="BridgeTagContainer")
        asset = ContainerReference(space="my_space", external_id="BridgeAssetContainer")
        view_to_exclude = ViewReference(space="my_space", external_id="BridgeTagView", version="v1")

        affected_without_exclude = resources.find_views_affected_by_requires(tag, asset)
        affected_with_exclude = resources.find_views_affected_by_requires(tag, asset, exclude_view=view_to_exclude)

        assert view_to_exclude not in affected_with_exclude, "Excluded view should not be in results"
        assert affected_with_exclude <= affected_without_exclude, "Results with exclude should be subset"

    def test_no_redundant_recommendations_when_path_exists(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that we don't recommend A→C when A→B→C already exists.

        This tests the transitive path check in get_missing_requires_for_view.
        If A can already reach C via B, recommending A→C is redundant.

        Scenario (from test data):
        - BridgeSiblingAContainer requires BridgeTagContainer
        - BridgeTagContainer requires BridgeSourceableContainer
        So: BridgeSiblingAContainer → BridgeTagContainer → BridgeSourceableContainer
        """
        resources = scenarios["requires-constraints"]

        sibling_a = ContainerReference(space="my_space", external_id="BridgeSiblingAContainer")
        tag = ContainerReference(space="my_space", external_id="BridgeTagContainer")
        sourceable = ContainerReference(space="my_space", external_id="BridgeSourceableContainer")

        # Verify the transitive path exists
        assert nx.has_path(resources.requires_graph, sibling_a, tag), "SiblingA should require Tag"
        assert nx.has_path(resources.requires_graph, tag, sourceable), "Tag should require Sourceable"
        assert nx.has_path(resources.requires_graph, sibling_a, sourceable), (
            "SiblingA should transitively require Sourceable"
        )

        # Get recommendations for a view with these containers
        missing = resources.get_missing_requires_for_view({sibling_a, tag, sourceable})

        # Should NOT recommend SiblingA → Sourceable (path already exists via Tag)
        sibling_a_to_sourceable = (sibling_a, sourceable)
        assert sibling_a_to_sourceable not in missing, (
            f"Should NOT recommend SiblingA → Sourceable (path already exists via Tag), got: {missing}"
        )

    @pytest.mark.parametrize(
        "lower_edge,higher_edge",
        [
            pytest.param(
                ("BridgeSiblingAContainer", "BridgeTagContainer"),  # existing transitivity
                ("BridgeTagContainer", "BridgeAssetContainer"),  # new edge
                id="existing-transitivity-cheaper-than-new-edge",
            ),
            pytest.param(
                ("BridgeTagContainer", "BridgeAssetContainer"),  # new edge
                ("BridgeTagContainer", "BridgeSiblingAContainer"),  # cycle-forming
                id="new-edge-cheaper-than-cycle",
            ),
            pytest.param(
                ("BridgeTagContainer", "BridgeAssetContainer"),  # higher coverage target
                ("BridgeTagContainer", "BridgeDescribableContainer"),  # lower coverage target
                id="higher-coverage-target-preferred",
            ),
        ],
    )
    def test_edge_weight_ordering(
        self,
        lower_edge: tuple[str, str],
        higher_edge: tuple[str, str],
        scenarios: dict[str, ValidationResources],
    ) -> None:
        """Test that edge weights have correct relative ordering for MST algorithm."""
        resources = scenarios["requires-constraints"]

        lower_src = ContainerReference(space="my_space", external_id=lower_edge[0])
        lower_dst = ContainerReference(space="my_space", external_id=lower_edge[1])
        higher_src = ContainerReference(space="my_space", external_id=higher_edge[0])
        higher_dst = ContainerReference(space="my_space", external_id=higher_edge[1])

        weight_lower = resources._compute_requires_edge_weight(lower_src, lower_dst)
        weight_higher = resources._compute_requires_edge_weight(higher_src, higher_dst)

        assert weight_lower > 0, f"Weight for {lower_edge} must be positive"
        assert weight_higher > 0, f"Weight for {higher_edge} must be positive"
        assert weight_lower < weight_higher, (
            f"{lower_edge} (weight={weight_lower}) should be cheaper than {higher_edge} (weight={weight_higher})"
        )

    def test_edge_weight_deterministic(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that edge weight computation is deterministic."""
        resources = scenarios["requires-constraints"]

        tag = ContainerReference(space="my_space", external_id="BridgeTagContainer")
        asset = ContainerReference(space="my_space", external_id="BridgeAssetContainer")

        weights = [resources._compute_requires_edge_weight(tag, asset) for _ in range(3)]
        assert len(set(weights)) == 1, "Weight computation should be deterministic"

    def test_edge_weight_cdf_source_forbidden(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that CDF built-in containers as sources get higher weight than user sources."""
        from cognite.neat._data_model._constants import CDF_BUILTIN_SPACES

        resources = scenarios["requires-constraints"]

        cdf_container = None
        user_container = None
        other_user_container = None
        for container in resources.requires_graph.nodes():
            if container.space in CDF_BUILTIN_SPACES:
                cdf_container = container
            elif user_container is None:
                user_container = container
            else:
                other_user_container = container
            if cdf_container and user_container and other_user_container:
                break

        if cdf_container and user_container and other_user_container:
            # CDF → user should be much more expensive than user → user
            weight_cdf_src = resources._compute_requires_edge_weight(cdf_container, user_container)
            weight_user_src = resources._compute_requires_edge_weight(other_user_container, user_container)

            assert weight_cdf_src > weight_user_src, (
                f"CDF source ({weight_cdf_src}) should be more expensive than user source ({weight_user_src})"
            )
