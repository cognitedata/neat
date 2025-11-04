from attr import dataclass

from cognite.neat._client.client import NeatClient
from cognite.neat._data_model.models.dms._data_types import DataType, DirectNodeRelation, Int32Property, Int64Property

from ._identifiers import NameSpace

XML_SCHEMA_NAMESPACE = NameSpace("http://www.w3.org/2001/XMLSchema#")

CDF_CDM_SPACE = "cdf_cdm"
CDF_CDM_VERSION = "v1"

COGNITE_CONCEPTS_MAIN = (
    "CogniteAsset",
    "CogniteEquipment",
    "CogniteActivity",
    "CogniteTimeSeries",
    "CogniteFile",
)

COGNITE_CONCEPTS_INTERFACES = (
    "CogniteDescribable",
    "CogniteSourceable",
    "CogniteSchedulable",
    "CogniteVisualizable",
)

COGNITE_CONCEPTS_CONFIGURATIONS = (
    "CogniteSourceSystem",
    "CogniteUnit",
    "CogniteAssetClass",
    "CogniteAssetType",
    "CogniteEquipmentType",
    "CogniteFileCategory",
)
COGNITE_CONCEPTS_ANNOTATIONS = (
    "CogniteAnnotation",
    "CogniteDiagramAnnotation",
)
COGNITE_CONCEPTS_3D = (
    "CogniteCubeMap",
    "CogniteCADRevision",
    "CognitePointCloudVolume",
    "Cognite360ImageAnnotation",
    "Cognite3DObject",
    "Cognite3DRevision",
    "Cognite360Image",
    "Cognite360ImageCollection",
    "Cognite360ImageStation",
    "CognitePointCloudModel",
    "Cognite3DTransformation",
    "Cognite360ImageModel",
    "Cognite3DModel",
    "CogniteCADModel",
    "CognitePointCloudRevision",
    "CogniteCADNode",
)

COGNITE_CONCEPTS: tuple[str, ...] = (
    *COGNITE_CONCEPTS_MAIN,
    *COGNITE_CONCEPTS_INTERFACES,
    *COGNITE_CONCEPTS_CONFIGURATIONS,
    *COGNITE_CONCEPTS_ANNOTATIONS,
    *COGNITE_CONCEPTS_3D,
)

COGNITE_SPACES = (CDF_CDM_SPACE,)


@dataclass(frozen=True)
class SpaceLimits:
    """Limits for spaces."""

    total: int = 100


@dataclass(frozen=True)
class ListPropertyLimits:
    """Limits for list properties."""

    default_direct_relations: int = 100
    default_other_types: int = 1_000
    max_int32_with_btree: int = 600
    max_int64_with_btree: int = 300
    max_all_other_types: int = 2_000


@dataclass(frozen=True)
class ContainerLimits:
    """Limits for containers."""

    total: int = 1_000
    properties_total: int = 25_000
    properties_per_container: int = 100
    enums_per_property: int = 32
    listable_property: ListPropertyLimits = ListPropertyLimits()

    def get_limit_for_data_type(self, data_type: DataType, has_btree_index: bool = False) -> int:
        """Get the limit for a specific data type."""
        if isinstance(data_type, DirectNodeRelation):
            return self.listable_property.default_direct_relations
        if isinstance(data_type, Int32Property) and has_btree_index:
            return self.listable_property.max_int32_with_btree
        if isinstance(data_type, Int64Property) and has_btree_index:
            return self.listable_property.max_int64_with_btree
        return self.listable_property.default_other_types


@dataclass(frozen=True)
class ViewLimits:
    """Limits for views."""

    total: int = 2_000
    versions_per_view: int = 100
    properties_per_view: int = 300
    implements_per_view: int = 10
    containers_per_view: int = 10


@dataclass(frozen=True)
class DataModelLimits:
    """Limits for data models."""

    versions_total: int = 500
    versions_per_data_model: int = 100
    views_per_data_model: int = 100


@dataclass(frozen=True)
class InstanceLimits:
    """Limits for instances."""

    live: int = 5_000_000
    soft_deleted: int = 10_000_000


class _DMSLimits:
    """CDF Data Modeling resource limits."""

    def __init__(self) -> None:
        self.space = SpaceLimits()
        self.container = ContainerLimits()
        self.view = ViewLimits()
        self.data_model = DataModelLimits()
        self.instance = InstanceLimits()

    def from_api_response(self, client: NeatClient) -> None:
        """Populate limits from API response."""
        # Implementation to parse and set limits from response can be added here
        ...


DMSDefaultLimits = _DMSLimits()
