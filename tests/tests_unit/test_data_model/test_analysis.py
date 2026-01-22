from typing import cast

import pytest
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat._data_model._analysis import (
    RequiresChangesForView,
    RequiresChangeStatus,
    ResourceSource,
    ValidationResources,
)
from cognite.neat._data_model._constants import CDF_CDM_SPACE
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.models.dms import ViewCorePropertyRequest, ViewReference, ViewRequest
from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._data_model import DataModelRequest
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._data_model.models.dms._references import ContainerReference, DataModelReference
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
        "requires-constraints-with-cdm": catalog.load_scenario(
            "requires_constraints",
            modus_operandi="additive",
            include_cdm=True,
            format="validation-resource",
        ),
        "requires-constraints-rebuild": catalog.load_scenario(
            "requires_constraints",
            modus_operandi="rebuild",  # Rebuild mode: CDF-only constraints not in merged
            include_cdm=True,  # Include real CDM containers with their requires constraints
            format="validation-resource",
        ),
        "cyclic_implements": catalog.load_scenario(
            "cyclic_implements",
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
    """Tests for requires constraint recommendations."""

    DEFAULT_SPACE = "my_space"
    DEFAULT_VERSION = "v1"

    def _space_for(self, name: str) -> str:
        """Return space for a container/view name. 'Cognite*' goes to CDM space."""
        return CDF_CDM_SPACE if name.startswith("Cognite") else self.DEFAULT_SPACE

    def _container_ref(self, name: str) -> ContainerReference:
        """Helper to create ContainerReference with default space."""
        return ContainerReference(space=self._space_for(name), external_id=name)

    def _view_ref(self, name: str) -> ViewReference:
        """Helper to create ViewReference with default space and version."""
        return ViewReference(space=self._space_for(name), external_id=name, version=self.DEFAULT_VERSION)

    def create_test_scenario(
        self,
        mapped_containers_by_view: dict[str, list[str]],
        requires_graph: dict[str, list[str]],
    ) -> ValidationResources:
        """Create a minimal ValidationResources for testing requires constraint logic.

        Args:
            mapped_containers_by_view: Dict mapping view names to list of container names
            requires_graph: Dict mapping container name to list of containers it requires.
                           Use "Target__auto" suffix to mark constraint as auto-generated.
                           Container names starting with "Cognite" are placed in CDM space.
        """
        # Collect all container names
        all_containers = set(requires_graph.keys())
        for containers in mapped_containers_by_view.values():
            all_containers.update(containers)
        for targets in requires_graph.values():
            all_containers.update(t.removesuffix("__auto") for t in targets)

        # Build containers
        containers = {}
        for name in all_containers:
            ref = self._container_ref(name)
            targets = requires_graph.get(name, [])
            constraints = {
                f"requires_{t.removesuffix('__auto')}{'__auto' if t.endswith('__auto') else ''}": {
                    "constraintType": "requires",
                    "require": {
                        "space": self._space_for(t.removesuffix("__auto")),
                        "externalId": t.removesuffix("__auto"),
                    },
                }
                for t in targets
            } or None
            containers[ref] = ContainerRequest.model_validate(
                {"space": ref.space, "externalId": ref.external_id, "properties": {}, "constraints": constraints}
            )

        # Build views
        views = {}
        for view_name, container_names in mapped_containers_by_view.items():
            ref = self._view_ref(view_name)
            props = {
                f"prop_{c}": {
                    "container": {"space": self._space_for(c), "externalId": c},
                    "containerPropertyIdentifier": f"prop_{c}",
                }
                for c in container_names
            }
            views[ref] = ViewRequest.model_validate(
                {"space": ref.space, "externalId": ref.external_id, "version": ref.version, "properties": props}
            )

        # Build data model
        dm_ref = DataModelReference(space=self.DEFAULT_SPACE, external_id="test_model", version=self.DEFAULT_VERSION)
        data_model = {
            dm_ref: DataModelRequest.model_validate(
                {
                    "space": self.DEFAULT_SPACE,
                    "externalId": "test_model",
                    "version": self.DEFAULT_VERSION,
                    "views": [{"space": v.space, "externalId": v.external_id, "version": v.version} for v in views],
                }
            )
        }

        local = SchemaSnapshot(data_model=data_model, views=views, containers=containers)
        return ValidationResources(modus_operandi="additive", local=local, cdf=SchemaSnapshot(), limits=SchemaLimits())

    @pytest.mark.parametrize(
        "mapped_containers_by_view,requires_graph,view_name,expected",
        [
            pytest.param(
                {"SingleContainerView": ["OnlyContainer"]},
                {},
                "SingleContainerView",
                RequiresChangesForView(set(), set(), RequiresChangeStatus.OPTIMAL),
                id="single-container-view-is-optimal",
            ),
            pytest.param(
                {"TagView": ["TagContainer", "AssetContainer"]},
                {"TagContainer": ["AssetContainer"]},
                "TagView",
                RequiresChangesForView(set(), set(), RequiresChangeStatus.OPTIMAL),
                id="already-optimal",
            ),
            pytest.param(
                {"TagView": ["CustomTag", "CustomAsset"], "AssetView": ["CustomAsset"]},
                {},
                "TagView",
                RequiresChangesForView(
                    to_add={
                        (
                            ContainerReference(space="my_space", external_id="CustomTag"),
                            ContainerReference(space="my_space", external_id="CustomAsset"),
                        )
                    },
                    to_remove=set(),
                    status=RequiresChangeStatus.CHANGES_AVAILABLE,
                ),
                id="missing-constraint",
            ),
            # Single-container view doesn't force CustomAsset as root - TagView is still solvable
            pytest.param(
                {"TagView": ["CustomTag", "CustomAsset"], "AssetView": ["CustomAsset"]},
                {},
                "TagView",
                RequiresChangesForView(
                    to_add={
                        (
                            ContainerReference(space="my_space", external_id="CustomTag"),
                            ContainerReference(space="my_space", external_id="CustomAsset"),
                        )
                    },
                    to_remove=set(),
                    status=RequiresChangeStatus.CHANGES_AVAILABLE,
                ),
                id="single-container-view-doesnt-force-root",
            ),
            # User container → CDM container (CDM containers are immutable)
            pytest.param(
                {"TagView": ["Tag", "CogniteAsset"]},
                {},
                "TagView",
                RequiresChangesForView(
                    to_add={
                        (
                            ContainerReference(space="my_space", external_id="Tag"),
                            ContainerReference(space=CDF_CDM_SPACE, external_id="CogniteAsset"),
                        )
                    },
                    to_remove=set(),
                    status=RequiresChangeStatus.CHANGES_AVAILABLE,
                ),
                id="missing-constraint-to-cdm",
            ),
            # Existing constraint is preserved (algorithm prefers existing edges)
            pytest.param(
                {"View": ["Root", "Leaf"]},
                {"Root": ["Leaf__auto"]},  # Existing auto constraint
                "View",
                RequiresChangesForView(set(), set(), RequiresChangeStatus.OPTIMAL),
                id="existing-auto-constraint-preserved",
            ),
            # User-intentional constraint is preserved
            pytest.param(
                {"View": ["Root", "Leaf"]},
                {"Leaf": ["Root"]},  # User-intentional (no __auto)
                "View",
                RequiresChangesForView(set(), set(), RequiresChangeStatus.OPTIMAL),
                id="existing-user-intentional-constraint-preserved",
            ),
            # Cycle: auto-constraint in cycle should be removed
            pytest.param(
                {"CycleView": ["CycleA", "CycleB"]},
                {"CycleA": ["CycleB__auto"], "CycleB": ["CycleA__auto"]},  # Bidirectional cycle
                "CycleView",
                RequiresChangesForView(
                    to_add=set(),
                    to_remove={
                        (
                            ContainerReference(space="my_space", external_id="CycleB"),
                            ContainerReference(space="my_space", external_id="CycleA"),
                        )
                    },
                    status=RequiresChangeStatus.CHANGES_AVAILABLE,
                ),
                id="cycle-auto-constraint-removed",
            ),
            # Wrong-direction auto constraint removed, user-intentional preserved
            pytest.param(
                {"View": ["A", "B", "C"]},
                {"C": ["B__auto"], "B": ["A"]},  # C→B auto (wrong dir), B→A user-intentional
                "View",
                RequiresChangesForView(
                    to_add={
                        (
                            ContainerReference(space="my_space", external_id="B"),
                            ContainerReference(space="my_space", external_id="C"),
                        )
                    },
                    to_remove={
                        (
                            ContainerReference(space="my_space", external_id="C"),
                            ContainerReference(space="my_space", external_id="B"),
                        )
                    },
                    status=RequiresChangeStatus.CHANGES_AVAILABLE,
                ),
                id="wrong-direction-auto-removed-user-intentional-preserved",
            ),
            # Star topology: root (1 view) requires leaves (2 views each) - Root selected as root
            pytest.param(
                {
                    "StarView": ["Root", "LeafA", "LeafB", "LeafC"],
                    "LeafAView": ["LeafA"],  # Extra views make leaves have view_count=2
                    "LeafBView": ["LeafB"],
                    "LeafCView": ["LeafC"],
                },
                {},
                "StarView",
                RequiresChangesForView(
                    to_add={
                        (
                            ContainerReference(space="my_space", external_id="Root"),
                            ContainerReference(space="my_space", external_id="LeafA"),
                        ),
                        (
                            ContainerReference(space="my_space", external_id="Root"),
                            ContainerReference(space="my_space", external_id="LeafB"),
                        ),
                        (
                            ContainerReference(space="my_space", external_id="Root"),
                            ContainerReference(space="my_space", external_id="LeafC"),
                        ),
                    },
                    to_remove=set(),
                    status=RequiresChangeStatus.CHANGES_AVAILABLE,
                ),
                id="star-topology-root-to-multiple-leaves",
            ),
        ],
    )
    def test_get_requires_changes_for_view(
        self,
        mapped_containers_by_view: dict[str, list[str]],
        requires_graph: dict[str, list[str]],
        view_name: str,
        expected: RequiresChangesForView,
    ) -> None:
        """Test get_requires_changes_for_view for isolated scenarios."""
        resources = self.create_test_scenario(mapped_containers_by_view, requires_graph)
        result = resources.get_requires_changes_for_view(self._view_ref(view_name))

        assert result.to_add == expected.to_add
        assert result.to_remove == expected.to_remove
        assert result.status == expected.status

    def test_views_by_container(self) -> None:
        """Test views_by_container returns correct view mappings."""
        resources = self.create_test_scenario(
            {"ViewA": ["SharedContainer", "OnlyA"], "ViewB": ["SharedContainer", "OnlyB"]},
            {},
        )

        # SharedContainer appears in both views
        shared = self._container_ref("SharedContainer")
        assert shared in resources.views_by_container
        view_ids = {v.external_id for v in resources.views_by_container[shared]}
        assert view_ids == {"ViewA", "ViewB"}

        # OnlyA appears only in ViewA
        only_a = self._container_ref("OnlyA")
        assert only_a in resources.views_by_container
        assert {v.external_id for v in resources.views_by_container[only_a]} == {"ViewA"}

    def test_containers_by_view(self) -> None:
        """Test containers_by_view returns correct container mappings."""
        resources = self.create_test_scenario(
            {"MyView": ["ContainerA", "ContainerB", "ContainerC"]},
            {},
        )

        view_ref = self._view_ref("MyView")
        assert view_ref in resources.containers_by_view
        container_ids = {c.external_id for c in resources.containers_by_view[view_ref]}
        assert container_ids == {"ContainerA", "ContainerB", "ContainerC"}

    @pytest.mark.parametrize(
        "mapped_containers_by_view,query_containers,expected_views",
        [
            pytest.param(
                {"ViewA": ["C1", "C2"], "ViewB": ["C2", "C3"]},
                ["C1", "C2"],
                {"ViewA"},
                id="containers-appear-together-in-one-view",
            ),
            pytest.param(
                {"ViewA": ["C1", "C2"], "ViewB": ["C3", "C4"]},
                ["C1", "C3"],
                set(),
                id="containers-never-together",
            ),
            pytest.param(
                {"ViewA": ["C1", "C2", "C3"], "ViewB": ["C1", "C2", "C3"]},
                ["C1", "C2"],
                {"ViewA", "ViewB"},
                id="containers-appear-together-in-multiple-views",
            ),
        ],
    )
    def test_find_views_mapping_to_containers(
        self,
        mapped_containers_by_view: dict[str, list[str]],
        query_containers: list[str],
        expected_views: set[str],
    ) -> None:
        """Test find_views_mapping_to_containers for various container combinations."""
        resources = self.create_test_scenario(mapped_containers_by_view, {})
        containers = [self._container_ref(c) for c in query_containers]
        shared_views = resources.find_views_mapping_to_containers(containers)
        view_ids = {v.external_id for v in shared_views}
        assert view_ids == expected_views

    def test_requires_constraint_graph_structure(self) -> None:
        """Test that requires_constraint_graph is built correctly for existing constraints."""
        resources = self.create_test_scenario(
            {"View": ["A", "B", "C"]},
            {"A": ["B"], "B": ["C"]},
        )
        graph = resources.requires_constraint_graph

        assert graph.has_edge(self._container_ref("A"), self._container_ref("B"))
        assert graph.has_edge(self._container_ref("B"), self._container_ref("C"))
        assert not graph.has_edge(self._container_ref("A"), self._container_ref("C"))

    def test_requires_constraint_cycles(self) -> None:
        """Test cycle detection in existing requires constraints."""
        resources = self.create_test_scenario(
            {"View": ["CycleA", "CycleB"]},
            {"CycleA": ["CycleB"], "CycleB": ["CycleA"]},
        )
        cycles = resources.requires_constraint_cycles

        assert len(cycles) == 1
        assert set(cycles[0]) == {self._container_ref("CycleA"), self._container_ref("CycleB")}

    @pytest.mark.parametrize(
        "requires_graph,query_containers,expected_complete",
        [
            pytest.param(
                {"A": ["B"]},  # A→B only, no path to C
                ["A", "B", "C"],
                False,
                id="incomplete-no-path-to-c",
            ),
            pytest.param(
                {},
                ["A"],
                True,
                id="single-container-always-complete",
            ),
            pytest.param(
                {"A": ["B"], "B": ["C"]},
                ["A", "B", "C"],
                True,
                id="complete-chain",
            ),
            pytest.param(
                {"A": ["B", "C"]},  # Star: A→B and A→C
                ["A", "B", "C"],
                True,
                id="complete-star",
            ),
        ],
    )
    def test_forms_directed_path(
        self,
        requires_graph: dict[str, list[str]],
        query_containers: list[str],
        expected_complete: bool,
    ) -> None:
        """Test forms_directed_path for various scenarios."""
        all_containers = set(query_containers)
        for src, targets in requires_graph.items():
            all_containers.add(src)
            all_containers.update(targets)
        resources = self.create_test_scenario(
            {"View": list(all_containers)},
            requires_graph,
        )
        container_refs = {self._container_ref(c) for c in query_containers}

        result = ValidationResources.forms_directed_path(container_refs, resources.requires_constraint_graph)
        assert result == expected_complete

    def test_requires_mst_has_no_spurious_cross_group_edges(self) -> None:
        """Verify MST doesn't connect containers that don't share a view."""
        resources = self.create_test_scenario(
            {
                "ViewA": ["GroupA_1", "GroupA_2"],
                "ViewB": ["GroupB_1", "GroupB_2"],
            },
            {},
        )

        group_a = {self._container_ref("GroupA_1"), self._container_ref("GroupA_2")}
        group_b = {self._container_ref("GroupB_1"), self._container_ref("GroupB_2")}

        for edge in resources.oriented_mst_edges:
            edge_set = set(edge)
            assert not (edge_set & group_a and edge_set & group_b), f"Cross-group edge was formed: {edge}"

    def test_requires_recommendations_baseline(
        self, scenarios: dict[str, ValidationResources], data_regression: DataRegressionFixture
    ) -> None:
        """Regression test for requires constraint recommendations."""
        resources = scenarios["requires-constraints-rebuild"]

        # Collect all recommendations sorted by view
        all_recommendations = {}

        for view_ref in sorted(resources.merged.views.keys(), key=lambda v: f"{v.space}:{v.external_id}"):
            containers = resources.containers_by_view.get(view_ref, set())
            if len(containers) < 2:
                continue

            changes = resources.get_requires_changes_for_view(view_ref)

            # Apply recommendations to get final state
            current = set()
            for src in containers:
                if src in resources.requires_constraint_graph:
                    for dst in resources.requires_constraint_graph.successors(src):
                        if dst in containers:
                            current.add((src, dst))

            final = current.copy()
            for edge in changes.to_add:
                final.add(edge)
            for edge in changes.to_remove:
                final.discard(edge)

            view_key = f"{view_ref.space}:{view_ref.external_id}({view_ref.version})"
            all_recommendations[view_key] = {
                "containers": sorted([c.external_id for c in containers]),
                "to_add": sorted([f"{src.external_id} -> {dst.external_id}" for src, dst in changes.to_add]),
                "to_remove": sorted([f"{src.external_id} -> {dst.external_id}" for src, dst in changes.to_remove]),
                "final_constraints": sorted([f"{src.external_id} -> {dst.external_id}" for src, dst in final]),
            }

        data_regression.check(all_recommendations)
