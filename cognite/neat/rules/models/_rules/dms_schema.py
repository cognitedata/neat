from abc import ABC
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from functools import total_ordering
from typing import ClassVar

from cognite.client import data_modeling as dm


@dataclass(frozen=True)
@total_ordering
class SchemaError(ABC):
    error_name: ClassVar[str]

    def __lt__(self, other: object) -> bool:
        if isinstance(other, SchemaError):
            return self.error_name < other.error_name
        return NotImplemented

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SchemaError):
            return self.error_name == other.error_name
        return NotImplemented


@dataclass
class DMSSchema:
    space: dm.SpaceApply
    model: dm.DataModelApply
    views: dm.ViewApplyList = field(default_factory=lambda: dm.ViewApplyList([]))
    containers: dm.ContainerApplyList = field(default_factory=lambda: dm.ContainerApplyList([]))
    node_types: dm.NodeApplyList = field(default_factory=lambda: dm.NodeApplyList([]))

    def validate(self) -> list[SchemaError]:
        errors: set[SchemaError] = set()
        defined_spaces = {self.space.space}
        defined_containers = {container.as_id(): container for container in self.containers}
        defined_views = {view.as_id() for view in self.views}

        for container in self.containers:
            if container.space not in defined_spaces:
                errors.add(MissingSpace(space=container.space, referred_by=container.as_id()))

        for view in self.views:
            view_id = view.as_id()
            if view.space not in defined_spaces:
                errors.add(MissingSpace(space=view.space, referred_by=view_id))

            for parent in view.implements or []:
                if parent not in defined_views:
                    errors.add(MissingParentView(view=parent, referred_by=view_id))

            for prop_name, prop in (view.properties or {}).items():
                if isinstance(prop, dm.MappedPropertyApply):
                    ref_container = defined_containers.get(prop.container)
                    if ref_container is None:
                        errors.add(MissingContainer(container=prop.container, referred_by=view_id))
                    elif prop.container_property_identifier not in ref_container.properties:
                        errors.add(
                            MissingContainerProperty(
                                container=prop.container,
                                property=prop.container_property_identifier,
                                referred_by=view_id,
                            )
                        )
                    else:
                        container_property = ref_container.properties[prop.container_property_identifier]

                        if isinstance(container_property.type, dm.DirectRelation) and prop.source is None:
                            errors.add(DirectRelationMissingSource(view_id=view_id, property=prop_name))
                elif isinstance(prop, dm.EdgeConnectionApply) and prop.source not in defined_views:
                    errors.add(MissingSourceView(view=prop.source, property=prop_name, referred_by=view_id))
                elif (
                    isinstance(prop, dm.EdgeConnectionApply)
                    and prop.edge_source is not None
                    and prop.edge_source not in defined_views
                ):
                    errors.add(MissingEdgeView(view=prop.edge_source, property=prop_name, referred_by=view_id))

            property_count = Counter(
                (prop.container, prop.container_property_identifier)
                for prop in (view.properties or {}).values()
                if isinstance(prop, dm.MappedPropertyApply)
            )
            for (container_id, container_property_identifier), count in property_count.items():
                if count > 1:
                    view_properties = [
                        prop_name
                        for prop_name, prop in (view.properties or {}).items()
                        if isinstance(prop, dm.MappedPropertyApply)
                        and (prop.container, prop.container_property_identifier)
                        == (container_id, container_property_identifier)
                    ]
                    errors.add(
                        ContainerPropertyUsedMultipleTimes(
                            container=container_id,
                            property=container_property_identifier,
                            referred_by=frozenset({(view_id, prop_name) for prop_name in view_properties}),
                        )
                    )

        if self.model.space not in defined_spaces:
            errors.add(MissingSpace(space=self.model.space, referred_by=self.model.as_id()))

        view_counts: dict[dm.ViewId, int] = defaultdict(int)
        for view in self.model.views or []:
            view_id = view if isinstance(view, dm.ViewId) else view.as_id()
            if view_id not in defined_views:
                errors.add(MissingView(referred_by=self.model.as_id(), view=view_id))
            view_counts[view_id] += 1

        for view_id, count in view_counts.items():
            if count > 1:
                errors.add(DuplicatedViewInDataModel(referred_by=self.model.as_id(), view=view_id))

        return list(errors)


@dataclass(frozen=True)
class MissingSpace(SchemaError):
    error_name: ClassVar[str] = "MissingSpace"
    space: str
    referred_by: dm.ContainerId | dm.ViewId | dm.NodeId | dm.EdgeId | dm.DataModelId


@dataclass(frozen=True)
class MissingContainer(SchemaError):
    error_name: ClassVar[str] = "MissingContainer"
    container: dm.ContainerId
    referred_by: dm.ViewId


@dataclass(frozen=True)
class MissingContainerProperty(SchemaError):
    error_name: ClassVar[str] = "MissingContainerProperty"
    container: dm.ContainerId
    property: str
    referred_by: dm.ViewId


@dataclass(frozen=True)
class MissingView(SchemaError):
    error_name: ClassVar[str] = "MissingView"
    view: dm.ViewId
    referred_by: dm.DataModelId | dm.ViewId


@dataclass(frozen=True)
class MissingParentView(MissingView):
    error_name: ClassVar[str] = "MissingParentView"
    referred_by: dm.ViewId


@dataclass(frozen=True)
class MissingSourceView(MissingView):
    error_name: ClassVar[str] = "MissingSourceView"
    property: str
    referred_by: dm.ViewId


@dataclass(frozen=True)
class MissingEdgeView(MissingView):
    error_name: ClassVar[str] = "MissingEdgeView"
    property: str
    referred_by: dm.ViewId


@dataclass(frozen=True)
class DuplicatedViewInDataModel(SchemaError):
    error_name: ClassVar[str] = "DuplicatedViewInDataModel"
    referred_by: dm.DataModelId
    view: dm.ViewId


@dataclass(frozen=True)
class DirectRelationMissingSource(SchemaError):
    error_name: ClassVar[str] = "DirectRelationMissingSource"
    view_id: dm.ViewId
    property: str


@dataclass(frozen=True)
class ContainerPropertyUsedMultipleTimes(SchemaError):
    error_name: ClassVar[str] = "ContainerPropertyUsedMultipleTimes"
    container: dm.ContainerId
    property: str
    referred_by: frozenset[tuple[dm.ViewId, str]]
