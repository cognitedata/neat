from typing import cast

import pytest
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat._data_model._analysis import ResourceSource, ValidationResources
from cognite.neat._data_model._constants import COGNITE_SPACES
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
            modus_operandi="additive",
            include_cdm=False,
            format="validation-resource",
        ),
        "cyclic_implements": catalog.load_scenario(
            "cyclic_implements",
            cdf_scenario_name="for_validators",
            modus_operandi="additive",
            include_cdm=False,
            format="validation-resource",
        ),
        "requires-constraints-with-cdm": catalog.load_scenario(
            "requires_constraints",
            modus_operandi="additive",
            include_cdm=True,  # Include real CDM containers with their requires constraints
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
    """Tests for requires constraint recommendations."""

    def test_views_by_container(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test views_by_container returns correct view mappings."""
        resources = scenarios["requires-constraints"]
        views_by_container = resources.views_by_container

        # Check a sample container mapping - Level02_SharedTagContainer appears in multiple views
        shared_tag = ContainerReference(space="my_space", external_id="Level02_SharedTagContainer")
        assert shared_tag in views_by_container
        shared_tag_views = views_by_container[shared_tag]
        assert any(v.external_id == "SharedTagView" for v in shared_tag_views)

    def test_containers_by_view(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test containers_by_view returns correct container mappings."""
        resources = scenarios["requires-constraints"]
        containers_by_view = resources.containers_by_view

        # Check a sample view mapping
        shared_tag_view = ViewReference(space="my_space", external_id="SharedTagView", version="v1")
        assert shared_tag_view in containers_by_view
        containers = containers_by_view[shared_tag_view]
        container_ids = {c.external_id for c in containers}
        assert container_ids == {
            "Level02_SharedAssetContainer",
            "Level02_SharedTagContainer",
            "Level03_SharedDescribableContainer",
        }

    @pytest.mark.parametrize(
        "container_ids,expect_found",
        [
            pytest.param(
                ["Level02_SharedTagContainer", "Level02_SharedAssetContainer"],
                {ViewReference(space="my_space", external_id="SharedTagView", version="v1")},
                id="containers-appear-together",
            ),
            pytest.param(
                ["DisconnectedGroupAContainer1", "DisconnectedGroupBContainer1"],
                set(),
                id="containers-never-together",
            ),
        ],
    )
    def test_find_views_mapping_to_containers(
        self,
        container_ids: list[str],
        expect_found: set[ViewReference],
        scenarios: dict[str, ValidationResources],
    ) -> None:
        """Test find_views_mapping_to_containers for various container combinations."""
        resources = scenarios["requires-constraints"]
        containers = [ContainerReference(space="my_space", external_id=cid) for cid in container_ids]
        shared_views = resources.find_views_mapping_to_containers(containers)
        assert shared_views == expect_found, f"Containers {container_ids}: expected {expect_found}, got {shared_views}"

    def test_requires_constraint_graph_structure(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that requires_constraint_graph is built correctly."""
        resources = scenarios["requires-constraints"]
        graph = resources.requires_constraint_graph

        # Check edges exist - ValveContainer requires TagWithWrongRequiresContainer
        valve = ContainerReference(space="my_space", external_id="Level01_ValveContainer")
        tag = ContainerReference(space="my_space", external_id="Level02_TagWithWrongRequiresContainer")
        assert graph.has_edge(valve, tag)

        # Check cycle edges
        cycle_a = ContainerReference(space="my_space", external_id="CycleContainerA")
        cycle_b = ContainerReference(space="my_space", external_id="CycleContainerB")
        assert graph.has_edge(cycle_a, cycle_b)
        assert graph.has_edge(cycle_b, cycle_a)

    def test_implements_cycles(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test cycle detection in requires constraints."""
        resources = scenarios["cyclic_implements"]
        cycles = resources.implements_cycles

        assert len(cycles) == 1
        assert set(cycles[0]) == {
            ViewReference(space="my_space", external_id="ViewA", version="v1"),
            ViewReference(space="my_space", external_id="ViewB", version="v1"),
            ViewReference(space="my_space", external_id="ViewC", version="v1"),
        }

    def test_requires_constraint_cycles(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test cycle detection in requires constraints."""
        resources = scenarios["requires-constraints"]
        cycles = resources.requires_constraint_cycles

        assert len(cycles) == 1
        assert set(cycles[0]) == {
            ContainerReference(space="my_space", external_id="CycleContainerB"),
            ContainerReference(space="my_space", external_id="CycleContainerA"),
        }

    @pytest.mark.parametrize(
        "containers,expected_complete",
        [
            pytest.param(
                ["Level01_ValveContainer", "Level03_DescribableContainer", "Level03_SourceableContainer"],
                False,
                id="incomplete-hierarchy",
            ),
            pytest.param(
                ["Level02_TagWithWrongRequiresContainer"],
                True,
                id="single-container-always-complete",
            ),
            pytest.param(
                ["Level02_AssetContainer", "Level03_DescribableContainer"],
                True,
                id="complete-with-requires",
            ),
        ],
    )
    def test_forms_directed_path(
        self,
        containers: list[str],
        expected_complete: bool,
        scenarios: dict[str, ValidationResources],
    ) -> None:
        """Test forms_directed_path for various scenarios."""
        resources = scenarios["requires-constraints"]
        container_refs = {ContainerReference(space="my_space", external_id=c) for c in containers}

        result = ValidationResources.forms_directed_path(container_refs, resources.requires_constraint_graph)
        assert result == expected_complete, f"Containers {containers}: expected {expected_complete}, got {result}"

    def test_external_non_cdm_containers_are_immutable(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that non-CDM containers from CDF are treated as immutable."""
        resources = scenarios["requires-constraints"]

        # ExternalOnlyContainer is in external_space (not CDM) but only defined in CDF
        external_container = ContainerReference(space="external_space", external_id="ExternalOnlyContainer")

        # Its requires constraint should be in the immutable graph
        immutable_graph = resources.immutable_requires_constraint_graph
        assert external_container in immutable_graph.nodes(), "Should be in immutable graph"

        # Verify the constraint: ExternalOnlyContainer → CogniteDescribable
        cognite_describable = ContainerReference(space="cdf_cdm", external_id="CogniteDescribable")
        assert immutable_graph.has_edge(external_container, cognite_describable), (
            "External container's requires constraint should be immutable"
        )

        # Edge forming cycle with external container should be forbidden
        weight = resources._compute_requires_edge_weight(cognite_describable, external_container)
        assert weight >= 1e9, f"Cycle with external container should be forbidden, got weight={weight}"

    def test_requires_mst_has_no_spurious_cross_group_edges(self, scenarios: dict[str, ValidationResources]) -> None:
        """Verify MST doesn't connect containers that never share a view."""
        resources = scenarios["requires-constraints"]

        group_a = {
            ContainerReference(space="my_space", external_id="DisconnectedGroupAContainer1"),
            ContainerReference(space="my_space", external_id="DisconnectedGroupAContainer2"),
        }
        group_b = {
            ContainerReference(space="my_space", external_id="DisconnectedGroupBContainer1"),
            ContainerReference(space="my_space", external_id="DisconnectedGroupBContainer2"),
        }

        for edge in resources.requires_mst:
            assert not (edge & group_a and edge & group_b), f"Cross-group edge was formed: {edge}"

    def test_to_remove_only_contains_non_mst_or_wrongly_oriented_edges(
        self, scenarios: dict[str, ValidationResources]
    ) -> None:
        """Test that to_remove contains only suboptimal or wrongly-oriented edges."""
        resources = scenarios["requires-constraints"]

        for view_ref in resources.merged.views:
            containers = resources.containers_by_view.get(view_ref, set())
            if len(containers) < 2:
                continue

            _, to_remove = resources.get_requires_changes_for_view(view_ref)

            for src, dst in to_remove:
                edge_undirected = frozenset({src, dst})
                is_in_mst = edge_undirected in resources.requires_mst
                has_correct_orientation = (src, dst) in resources.oriented_requires_mst

                # Edge should be removed if it's either:
                # - Not in MST at all, OR
                # - In MST but wrong orientation
                assert not is_in_mst or not has_correct_orientation, (
                    f"View {view_ref}: edge {src.external_id} → {dst.external_id} "
                    f"is in to_remove but is in MST with correct orientation - should not remove!"
                )

    def test_cdf_containers_are_never_sources_in_add_recommendations(
        self, scenarios: dict[str, ValidationResources]
    ) -> None:
        """Test that CDF containers are never recommended as sources for new constraints."""
        resources = scenarios["requires-constraints-with-cdm"]

        for view_ref in resources.merged.views:
            to_add, _ = resources.get_requires_changes_for_view(view_ref)

            for src, dst in to_add:
                assert src.space not in COGNITE_SPACES, (
                    f"CDF container {src} should not be a source in add recommendations. "
                    f"Found: {src} -> {dst} for view {view_ref}"
                )

    def test_recommendations_based_on_local_not_merged(self, scenarios: dict[str, ValidationResources]) -> None:
        """Test that recommendations diff against LOCAL schema, not merged.

        Scenario: ValveContainer exists in both local and CDF with DIFFERENT constraints:
        - Local has: ValveContainer → TagWithWrongRequiresContainer
        - CDF has: ValveContainer → CogniteDescribable

        Merged would have BOTH constraints. But recommendations should be based on LOCAL only:
        - CDF-only constraint should NOT appear in to_remove
        """
        resources = scenarios["requires-constraints"]

        valve_container = ContainerReference(space="my_space", external_id="Level01_ValveContainer")
        describable = ContainerReference(space="cdf_cdm", external_id="CogniteDescribable")

        # Verify the test setup: CDF has constraint that local doesn't
        assert valve_container in resources.cdf.containers, "Test setup: ValveContainer should be in CDF"
        cdf_container = resources.cdf.containers[valve_container]
        assert cdf_container.constraints, "Test setup: CDF ValveContainer should have constraints"

        local_container = resources.local.containers[valve_container]
        local_constraint_targets = {
            c.require for c in (local_container.constraints or {}).values() if hasattr(c, "require")
        }
        assert describable not in local_constraint_targets, (
            "Test setup: Local ValveContainer should NOT have constraint to CogniteDescribable"
        )

        # Get recommendations for ValveView
        view_ref = ViewReference(space="my_space", external_id="ValveView", version="v1")
        to_add, to_remove = resources.get_requires_changes_for_view(view_ref)

        # The key assertion: to_remove should only contain constraints from LOCAL
        # The CDF-only constraint (ValveContainer → CogniteDescribable) should NOT be in to_remove
        to_remove_edges = {(src.external_id, dst.external_id) for src, dst in to_remove}
        assert ("Level01_ValveContainer", "CogniteDescribable") not in to_remove_edges, (
            "to_remove should not include CDF-only constraints"
        )

    def test_requires_recommendations_baseline(
        self, scenarios: dict[str, ValidationResources], data_regression: DataRegressionFixture
    ) -> None:
        """Regression test for requires constraint recommendations."""
        resources = scenarios["requires-constraints-with-cdm"]

        # Collect all recommendations sorted by view
        all_recommendations = {}

        for view_ref in sorted(resources.merged.views.keys(), key=lambda v: f"{v.space}:{v.external_id}"):
            containers = resources.containers_by_view.get(view_ref, set())
            if len(containers) < 2:
                continue

            to_add, to_remove = resources.get_requires_changes_for_view(view_ref)

            # Apply recommendations to get final state
            current = set()
            for src in containers:
                if src in resources.requires_constraint_graph:
                    for dst in resources.requires_constraint_graph.successors(src):
                        if dst in containers:
                            current.add((src, dst))

            final = current.copy()
            for edge in to_add:
                final.add(edge)
            for edge in to_remove:
                final.discard(edge)

            view_key = f"{view_ref.space}:{view_ref.external_id}({view_ref.version})"
            all_recommendations[view_key] = {
                "containers": sorted([c.external_id for c in containers]),
                "to_add": sorted([f"{src.external_id} -> {dst.external_id}" for src, dst in to_add]),
                "to_remove": sorted([f"{src.external_id} -> {dst.external_id}" for src, dst in to_remove]),
                "final_constraints": sorted([f"{src.external_id} -> {dst.external_id}" for src, dst in final]),
            }

        data_regression.check(all_recommendations)
