from abc import ABC, abstractmethod
from dataclasses import dataclass
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
    ) -> None:
        self.local_resources = local_resources
        self.cdf_resources = cdf_resources

    @abstractmethod
    def run(self) -> list[ConsistencyError] | list[Recommendation] | list[ConsistencyError | Recommendation]:
        """Execute the success handler on the data model."""
        # do something with data model
        ...
