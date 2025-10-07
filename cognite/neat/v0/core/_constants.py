import re
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.ids import DataModelId
from rdflib import DC, DCTERMS, FOAF, OWL, RDF, RDFS, SH, SKOS, XSD, Namespace, URIRef
from rdflib.namespace import DefinedNamespace

from cognite import neat

if TYPE_CHECKING:
    from cognite.neat.v0.core._data_model.models.physical import PhysicalProperty


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

COGNITE_CONCEPTS = (
    "CogniteAsset",
    "CogniteEquipment",
    "CogniteActivity",
    "CogniteTimeSeries",
    "CogniteFile",
    "CogniteDescribable",
    "CogniteSourceable",
    "CogniteSchedulable",
    "CogniteVisualizable",
    "CogniteSourceSystem",
    "CogniteUnit",
    "CogniteAssetClass",
    "CogniteAssetType",
    "CogniteEquipmentType",
    "CogniteFileCategory",
    "CogniteAnnotation",
    "CogniteDiagramAnnotation",
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

DMS_LISTABLE_PROPERTY_LIMIT = 1000

EXAMPLE_DATA_MODELS = PACKAGE_DIRECTORY / "core" / "_data_model" / "examples"
EXAMPLE_GRAPHS = PACKAGE_DIRECTORY / "core" / "_instances" / "examples"

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

# The number of instances that should be left as a margin when Neat writes to CDF through the DMS API.
# This is currently set conservatively to 1 million. The reasoning for this is that there are CDF
# applications such as Infield and Industrial Canvas that can write to the DMS API, as well as likely third-party
# applications that can write to the DMS API. If Neat fills up the entire capacity, these type of data gathering
# applications will experience data loss. The limit of 1 million is chosen such that it will trigger alarms in the
# CDF projects, such that admins can take action to increase or clean up the capacity before it is too late.
DMS_INSTANCE_LIMIT_MARGIN = 1_000_000

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

BASE_MODEL = Literal["CogniteCore"]


def get_asset_read_only_properties_with_connection() -> "list[PhysicalProperty]":
    """Gets the asset read-only properties with connection, i.e. Root and Path."""
    from cognite.neat.v0.core._data_model.models.physical import PhysicalProperty

    return [PhysicalProperty.model_validate(item) for item in (_ASSET_ROOT_PROPERTY, _ASSET_PATH_PROPERTY)]


def get_base_concepts(
    base_model: BASE_MODEL = "CogniteCore",
    total_concepts: int | None = None,
) -> list[str]:
    """Gets the base concepts for a given base model represented in the short form.
    Args:
        base_model: The base model to get the concepts for.
        total_concepts: The number of concepts to get. If None, all concepts are returned.
    """
    # Local import to avoid circular dependency issues
    from cognite.neat.v0.core._issues.errors._general import NeatValueError

    if base_model == "CogniteCore":
        return [f"cdf_cdm:{concept}(version=v1)" for concept in COGNITE_CONCEPTS][:total_concepts]
    else:
        raise NeatValueError(f"Base model <{base_model}> is not supported")


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


def cognite_prefixes() -> dict[str, Namespace]:
    """Returns the Cognite prefixes and namespaces."""
    return {space: Namespace(CDF_NAMESPACE[space] + "/") for space in COGNITE_SPACES}


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

NAMED_GRAPH_NAMESPACE = Namespace("http://thisisneat.io/namedgraph/")
