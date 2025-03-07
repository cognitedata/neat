import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.ids import DataModelId
from rdflib import DC, DCTERMS, FOAF, OWL, RDF, RDFS, SH, SKOS, XSD, Namespace, URIRef
from rdflib.namespace import DefinedNamespace

from cognite import neat

if TYPE_CHECKING:
    from cognite.neat._rules.models.dms import DMSProperty


def _is_in_notebook() -> bool:
    try:
        from IPython import get_ipython

        if "IPKernelApp" not in get_ipython().config:  # pragma: no cover
            return False
    except ImportError:
        return False
    except AttributeError:
        return False
    return True


def _is_in_browser() -> bool:
    try:
        from pyodide.ffi import IN_BROWSER  # type: ignore [import-not-found]
    except ModuleNotFoundError:
        return False
    return IN_BROWSER


IN_PYODIDE = _is_in_browser()
IN_NOTEBOOK = _is_in_notebook() or IN_PYODIDE


PACKAGE_DIRECTORY = Path(neat.__file__).parent
COGNITE_MODELS = (
    DataModelId("cdf_cdm", "CogniteCore", "v1"),
    DataModelId("cdf_idm", "CogniteProcessIndustries", "v1"),
)
COGNITE_SPACES = frozenset(
    {model.space for model in COGNITE_MODELS}
    | {
        "cdf_360_image_schema",
        "cdf_3d_schema",
        "cdf_apm",
        "cdf_apps_shared",
        "cdf_cdm",
        "cdf_cdm_3d",
        "cdf_cdm_units",
        "cdf_classic",
        "cdf_core",
        "cdf_extraction_extensions",
        "cdf_idm",
        "cdf_industrial_canvas",
        "cdf_infield",
        "cdf_time_series_data",
        "cdf_units",
    }
)

COGNITE_CORE_CONCEPTS = frozenset(
    {
        "CogniteFile",
        "CogniteCubeMap",
        "CogniteCADRevision",
        "CognitePointCloudVolume",
        "Cognite360ImageAnnotation",
        "CogniteAnnotation",
        "CogniteUnit",
        "CogniteAsset",
        "Cognite3DObject",
        "Cognite3DRevision",
        "Cognite360Image",
        "CogniteDiagramAnnotation",
        "Cognite360ImageCollection",
        "Cognite360ImageStation",
        "CognitePointCloudModel",
        "CogniteTimeSeries",
        "Cognite3DTransformation",
        "CogniteEquipment",
        "Cognite360ImageModel",
        "CogniteAssetClass",
        "CogniteAssetType",
        "CogniteEquipmentType",
        "Cognite3DModel",
        "CogniteCADModel",
        "CognitePointCloudRevision",
        "CogniteCADNode",
        "CogniteFileCategory",
        "CogniteActivity",
    }
)


COGNITE_CORE_FEATURES = frozenset(
    {
        "CogniteDescribable",
        "CogniteSourceable",
        "CogniteSourceSystem",
        "CogniteSchedulable",
        "CogniteVisualizable",
    }
)

COGNITE_3D_CONCEPTS = frozenset(
    {
        "Cognite3DModel",
        "Cognite3DObject",
        "Cognite3DRevision",
        "Cognite3DTransformation",
        "Cognite360Image",
        "Cognite360ImageAnnotation",
        "Cognite360ImageCollection",
        "Cognite360ImageModel",
        "Cognite360ImageStation",
        "CogniteCADModel",
        "CogniteCADNode",
        "CogniteCADRevision",
        "CogniteCubeMap",
        "CognitePointCloudModel",
        "CognitePointCloudRevision",
        "CognitePointCloudVolume",
    }
)

COGNITE_ANNOTATION = frozenset(
    {
        "CogniteAnnotation",
        "CogniteDiagramAnnotation",
    }
)

DMS_LISTABLE_PROPERTY_LIMIT = 1000

EXAMPLE_RULES = PACKAGE_DIRECTORY / "_rules" / "examples"
EXAMPLE_GRAPHS = PACKAGE_DIRECTORY / "_graph" / "examples"
EXAMPLE_WORKFLOWS = PACKAGE_DIRECTORY / "_workflows" / "examples"

DEFAULT_SPACE_URI = "http://purl.org/cognite/space/{space}#"
SPACE_URI_PATTERN = re.compile(r"http://purl.org/cognite/space/(?P<space>[^#]+)#$")
DEFAULT_RAW_URI = "http://purl.org/cognite/raw#"
DEFAULT_NAMESPACE = Namespace("http://purl.org/cognite/neat/")
CDF_NAMESPACE = Namespace("https://cognitedata.com/")
DEFAULT_BASE_URI = URIRef(DEFAULT_NAMESPACE)
CLASSIC_CDF_NAMESPACE = Namespace("http://purl.org/cognite/cdf-classic#")
XML_SCHEMA_NAMESPACE = Namespace("http://www.w3.org/2001/XMLSchema#")


class NEAT(DefinedNamespace):
    """
    NEAT internal data model used for internal purposes of the NEAT library

    """

    _fail = True
    _NS = Namespace("http://thisisneat.io/internal/")

    UnknownType: URIRef  # Unknown type used to express that the type of a subject is unknown
    EmptyType: URIRef  # Empty type used to express that the type of a subject is empty


def get_default_prefixes_and_namespaces() -> dict[str, Namespace]:
    return {
        "owl": OWL._NS,
        "rdf": RDF._NS,
        "rdfs": RDFS._NS,
        "dcterms": DCTERMS._NS,
        "dc": DC._NS,
        "skos": SKOS._NS,
        "sh": SH._NS,
        "xsd": XSD._NS,
        "imf": Namespace("http://ns.imfid.org/imf#"),
        "pav": Namespace("http://purl.org/pav/"),
        "foaf": FOAF._NS,
        "dexpi": Namespace("http://sandbox.dexpi.org/rdl/"),
        "qudt": Namespace("https://qudt.org/vocab/unit/"),
        "iodd": Namespace("http://www.io-link.com/IODD/2010/10/"),
        "aml": Namespace("https://www.automationml.org/"),
    }


DEFAULT_URI = ""

DEFAULT_DOCS_URL = "https://cognite-neat.readthedocs-hosted.com/en/latest/"

# These are the API limits for the DMS API, https://docs.cognite.com/cdf/dm/dm_reference/dm_limits_and_restrictions
DMS_CONTAINER_PROPERTY_SIZE_LIMIT = 100
DMS_VIEW_CONTAINER_SIZE_LIMIT = 10
DMS_DIRECT_RELATION_LIST_DEFAULT_LIMIT = 100
DMS_PRIMITIVE_LIST_DEFAULT_LIMIT = 1000
DMS_CONTAINER_LIST_MAX_LIMIT = 2000

_ASSET_ROOT_PROPERTY = {
    "connection": "direct",
    "container": "cdf_cdm:CogniteAsset",
    "container_property": "assetHierarchy_root",
    "description": "An automatically updated reference to the top-level asset of the hierarchy.",
    "immutable": False,
    "is_list": False,
    "name": "Root",
    "nullable": True,
    "value_type": "cdf_cdm:CogniteAsset(version=v1)",
    "view": "cdf_cdm:CogniteAsset(version=v1)",
    "view_property": "root",
}

_ASSET_PATH_PROPERTY = {
    "connection": "direct",
    "container": "cdf_cdm:CogniteAsset",
    "container_property": "assetHierarchy_path",
    "description": (
        "An automatically updated ordered list of this asset's ancestors, starting with the root asset. "
        "Enables subtree filtering to find all assets under a parent."
    ),
    "immutable": False,
    "is_list": True,
    "name": "Path",
    "nullable": True,
    "value_type": "cdf_cdm:CogniteAsset(version=v1)",
    "view": "cdf_cdm:CogniteAsset(version=v1)",
    "view_property": "path",
}


def get_asset_read_only_properties_with_connection() -> "list[DMSProperty]":
    """Gets the asset read-only properties with connection, i.e. Root and Path."""
    from cognite.neat._rules.models.dms import DMSProperty

    return [DMSProperty.model_validate(item) for item in (_ASSET_ROOT_PROPERTY, _ASSET_PATH_PROPERTY)]


READONLY_PROPERTIES_BY_CONTAINER: Mapping[dm.ContainerId, frozenset[str]] = {
    dm.ContainerId("cdf_cdm", "CogniteAsset"): frozenset(
        {"assetHierarchy_root", "assetHierarchy_path", "assetHierarchy_path_last_updated_time"}
    ),
    dm.ContainerId("cdf_cdm", "CogniteFile"): frozenset({"isUploaded", "uploadedTime"}),
}

HIERARCHICAL_PROPERTIES_BY_CONTAINER: Mapping[dm.ContainerId, frozenset[str]] = {
    dm.ContainerId("cdf_cdm", "CogniteAsset"): frozenset({"assetHierarchy_parent"})
}


def is_readonly_property(container: dm.ContainerId, property_: str) -> bool:
    return container in READONLY_PROPERTIES_BY_CONTAINER and property_ in READONLY_PROPERTIES_BY_CONTAINER[container]


def is_hierarchy_property(container: dm.ContainerId, property_: str) -> bool:
    return (
        container in HIERARCHICAL_PROPERTIES_BY_CONTAINER
        and property_ in HIERARCHICAL_PROPERTIES_BY_CONTAINER[container]
    )


DMS_RESERVED_PROPERTIES = frozenset(
    {
        "createdTime",
        "deletedTime",
        "edge_id",
        "extensions",
        "externalId",
        "lastUpdatedTime",
        "node_id",
        "project_id",
        "property_group",
        "seq",
        "space",
        "version",
        "tg_table_name",
        "startNode",
        "endNode",
    }
)
