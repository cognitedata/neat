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
