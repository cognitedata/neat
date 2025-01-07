from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.ids import DataModelId
from rdflib import DC, DCTERMS, FOAF, OWL, RDF, RDFS, SH, SKOS, XSD, Namespace, URIRef

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
DMS_LISTABLE_PROPERTY_LIMIT = 1000

EXAMPLE_RULES = PACKAGE_DIRECTORY / "_rules" / "examples"
EXAMPLE_GRAPHS = PACKAGE_DIRECTORY / "_graph" / "examples"
EXAMPLE_WORKFLOWS = PACKAGE_DIRECTORY / "_workflows" / "examples"

DEFAULT_SPACE_URI = "http://purl.org/cognite/{space}#"
DEFAULT_NAMESPACE = Namespace("http://purl.org/cognite/neat/")
CDF_NAMESPACE = Namespace("https://cognitedata.com/")
DEFAULT_BASE_URI = URIRef(DEFAULT_NAMESPACE)
CLASSIC_CDF_NAMESPACE = Namespace("http://purl.org/cognite/cdf-classic#")
UNKNOWN_TYPE = DEFAULT_NAMESPACE.UnknownType
XML_SCHEMA_NAMESPACE = Namespace("http://www.w3.org/2001/XMLSchema#")


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

DMS_CONTAINER_PROPERTY_SIZE_LIMIT = 100
DMS_VIEW_CONTAINER_SIZE_LIMIT = 10
DMS_DIRECT_RELATION_LIST_LIMIT = 100

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


def is_readonly_property(container: dm.ContainerId, property_: str) -> bool:
    return container in READONLY_PROPERTIES_BY_CONTAINER and property_ in READONLY_PROPERTIES_BY_CONTAINER[container]
