from abc import ABC, abstractmethod
from dataclasses import dataclass
from itertools import chain
from typing import ClassVar, TypeAlias

from cognite.neat._data_model.models.dms._container import ContainerRequest
from cognite.neat._data_model.models.dms._references import (
    ContainerDirectReference,
    ContainerReference,
    DataModelReference,
    ViewDirectReference,
    ViewReference,
)
from cognite.neat._data_model.models.dms._views import ViewRequest
from cognite.neat._issues import ConsistencyError, Recommendation
from cognite.neat._utils.useful_types import ModusOperandi

# Type aliases for better readability
ViewsByReference: TypeAlias = dict[ViewReference, ViewRequest]
ContainersByReference: TypeAlias = dict[ContainerReference, ContainerRequest]
AncestorsByReference: TypeAlias = dict[ViewReference, set[ViewReference]]
ReverseToDirectMapping: TypeAlias = dict[
    tuple[ViewReference, str], tuple[ViewReference, ContainerDirectReference | ViewDirectReference]
]
ConnectionEndNodeTypes: TypeAlias = dict[tuple[ViewReference, str], ViewReference]


@dataclass
class LocalResources:
    """Local data model resources."""

    data_model_reference: DataModelReference
    views_by_reference: ViewsByReference
    ancestors_by_view_reference: AncestorsByReference
    reverse_to_direct_mapping: ReverseToDirectMapping
    containers_by_reference: ContainersByReference
    connection_end_node_types: ConnectionEndNodeTypes


@dataclass
class CDFResources:
    """CDF resources."""

    views_by_reference: ViewsByReference
    ancestors_by_view_reference: AncestorsByReference
    containers_by_reference: ContainersByReference


class DataModelValidator(ABC):
    """Assessors for fundamental data model principles."""

    code: ClassVar[str]

    def __init__(
        self,
        local_resources: LocalResources,
        cdf_resources: CDFResources,
        modus_operandi: ModusOperandi = "additive",
    ) -> None:
        self.local_resources = local_resources
        self.cdf_resources = cdf_resources
        self.modus_operandi = modus_operandi

    @abstractmethod
    def run(self) -> list[ConsistencyError] | list[Recommendation] | list[ConsistencyError | Recommendation]:
        """Execute the success handler on the data model."""
        # do something with data model
        ...

    def _select_view(self, view_ref: ViewReference, property_: str) -> ViewRequest | None:
        """Select the appropriate view (local or CDF) that contains desired property.

        Prioritizes views that contain the property  (first local than CDF),
        then falls back to any available view (even without the property).

        Args:
            view_ref: Reference to the view.
            property_: Property name to look for.

        """
        local_view = self.local_resources.views_by_reference.get(view_ref)
        cdf_view = self.cdf_resources.views_by_reference.get(view_ref)

        # Try views with the property first, then any available view
        candidates = chain(
            (v for v in (local_view, cdf_view) if v and v.properties and property_ in v.properties),
            (v for v in (local_view, cdf_view) if v),
        )

        return next(candidates, None)

    def _select_container(self, container_ref: ContainerReference, property_: str) -> ContainerRequest | None:
        """Select the appropriate container (local or CDF) that contains the desired property.

        Prioritizes containers that contain the property (first local than CDF),
        then falls back to any available container.

        Args:
            container_ref: Reference to the container.
            property_: Property name to look for.
        """
        local_container = self.local_resources.containers_by_reference.get(container_ref)
        cdf_container = self.cdf_resources.containers_by_reference.get(container_ref)

        # Try containers with the property first, then any available container
        candidates = chain(
            (c for c in (local_container, cdf_container) if c and c.properties and property_ in c.properties),
            (c for c in (local_container, cdf_container) if c),
        )

        return next(candidates, None)
