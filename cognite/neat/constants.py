from pathlib import Path

from rdflib import DCTERMS, OWL, RDF, RDFS, SKOS, XSD, Namespace

from cognite import neat

PACKAGE_DIRECTORY = Path(neat.__file__).parent


EXAMPLE_RULES = PACKAGE_DIRECTORY / "legacy" / "rules" / "examples"
EXAMPLE_GRAPHS = PACKAGE_DIRECTORY / "legacy" / "graph" / "examples"
_OLD_WORKFLOWS = PACKAGE_DIRECTORY / "legacy" / "workflows" / "examples"
EXAMPLE_WORKFLOWS = PACKAGE_DIRECTORY / "workflows" / "examples"

DEFAULT_NAMESPACE = Namespace("http://purl.org/cognite/neat#")

PREFIXES = {
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
