"""These are user modeling warnings. These warnings will not cause the resulting model
to be invalid, but will likely lead to suboptimal performance, unnecessary complexity,
or other issues."""
# These warnings are usually only used once in the code base.

from dataclasses import dataclass

from cognite.client.data_classes.data_modeling import ContainerId, ViewId

from cognite.neat.rules.models._constants import DMS_CONTAINER_PROPERTY_SIZE_LIMIT

from ._models import UserModelingWarning

__all__ = [
    "DirectRelationMissingSourceWarning",
    "EmptyContainerWarning",
    "HasDataFilterOnNoPropertiesViewWarning",
    "NodeTypeFilterOnParentViewWarning",
    "HasDataFilterOnViewWithReferencesWarning",
    "ViewPropertyLimitWarning",
    "NotNeatSupportedFilterWarning",
    "ParentInDifferentSpaceWarning",
]


@dataclass(frozen=True)
class DirectRelationMissingSourceWarning(UserModelingWarning):
    """The view {view_id}.{prop_name} is a direct relation without a source.
    Direct relations in views should point to a single other view, if not, you end up
    with a more complex model than necessary."""

    fix = "Create the source view"

    view_id: ViewId
    prop_name: str


@dataclass(frozen=True)
class ParentInDifferentSpaceWarning(UserModelingWarning):
    """The view {view_id} has multiple parents in different spaces.
    Neat recommends maximum one implementation of a view from another space."""

    fix = "Ensure all parents of the view are in the same space"

    view_id: ViewId


@dataclass(frozen=True)
class EmptyContainerWarning(UserModelingWarning):
    """Container {container_id} is empty and will be skipped.
    The container does not have any properties."""

    fix = "Add properties to the container or remove the container"

    container_id: ContainerId


@dataclass(frozen=True)
class HasDataFilterOnNoPropertiesViewWarning(UserModelingWarning):
    """Cannot set hasData filter on view {view_id}.
    The view does not have properties in any containers.
    Use a node type filter instead."""

    fix = "Use a node type filter instead"

    view_id: ViewId


@dataclass(frozen=True)
class NodeTypeFilterOnParentViewWarning(UserModelingWarning):
    """Setting a node type filter on parent view {view_id}.
    This is not recommended as parent views are typically used for multiple types of nodes."""

    fix = "Use a HasData filter instead"

    view_id: ViewId


@dataclass(frozen=True)
class HasDataFilterOnViewWithReferencesWarning(UserModelingWarning):
    """Setting a hasData filter on view {view_id} which references other views {references}.
    This is not recommended as it will lead to no nodes being returned when querying the solution view.
    Use a NodeType filter instead."""

    fix = "Use a NodeType filter instead"

    view_id: ViewId
    references: frozenset[ViewId]


@dataclass(frozen=True)
class ViewPropertyLimitWarning(UserModelingWarning):
    """The number of properties in the {view_id} view is {count} which
    is more than the API limit {limit} properties.
    This can lead to performance issues.
    Reduce the number of properties in the view."""

    fix = "Reduce the number of properties in the view"

    view_id: ViewId
    count: int
    limit: int = DMS_CONTAINER_PROPERTY_SIZE_LIMIT


@dataclass(frozen=True)
class NotNeatSupportedFilterWarning(UserModelingWarning):
    """The view {view_id} uses a non-standard filter.
    This will not be validated by Neat, and is thus not recommended.
    If you can use a HasData or NoteType filter."""

    fix = "Use a HasData or NoteType filter instead"

    view_id: ViewId
