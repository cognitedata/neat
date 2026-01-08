from ._identifiers import NameSpace

XML_SCHEMA_NAMESPACE = NameSpace("http://www.w3.org/2001/XMLSchema#")

CDF_CDM_SPACE = "cdf_cdm"
CDF_IDM_SPACE = "cdf_idm"
CDF_CDM_3D_SPACE = "cdf_cdm_3d"
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

# Legacy constant - used by v0 code, only includes CDM space
COGNITE_SPACES = (CDF_CDM_SPACE,)

# All CDF built-in spaces that contain system containers/views (not user-modifiable)
CDF_BUILTIN_SPACES = frozenset({CDF_CDM_SPACE, CDF_IDM_SPACE, CDF_CDM_3D_SPACE})

# Defaults from https://docs.cognite.com/cdf/dm/dm_reference/dm_limits_and_restrictions#list-size-limits

DEFAULT_MAX_LIST_SIZE = 1000
DEFAULT_MAX_LIST_SIZE_DIRECT_RELATIONS = 100
