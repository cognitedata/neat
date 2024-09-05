from pathlib import Path

from rdflib import DCTERMS, OWL, RDF, RDFS, SKOS, XSD, Namespace

from cognite import neat

PACKAGE_DIRECTORY = Path(neat.__file__).parent


EXAMPLE_RULES = PACKAGE_DIRECTORY / "rules" / "examples"
EXAMPLE_GRAPHS = PACKAGE_DIRECTORY / "graph" / "examples"
EXAMPLE_WORKFLOWS = PACKAGE_DIRECTORY / "workflows" / "examples"

DEFAULT_SPACE_URI = "http://purl.org/cognite/{space}#"
DEFAULT_NAMESPACE = Namespace("http://purl.org/cognite/neat#")


def get_default_prefixes() -> dict[str, Namespace]:
    return {
        "rdf": RDF._NS,
        "rdfs": RDFS._NS,
        "dct": DCTERMS._NS,
        "skos": SKOS._NS,
        "owl": OWL._NS,
        "xsd": XSD._NS,
        "pav": Namespace("http://purl.org/pav/"),
    }


DEFAULT_URI = ""

DEFAULT_DOCS_URL = "https://cognite-neat.readthedocs-hosted.com/en/latest/"

DMS_CONTAINER_PROPERTY_SIZE_LIMIT = 100
DMS_VIEW_CONTAINER_SIZE_LIMIT = 10
