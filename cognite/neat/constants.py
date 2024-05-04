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
    "cim": Namespace("http://iec.ch/TC57/2013/CIM-schema-cim16#"),
    "icim": Namespace("http://iec.ch/TC57/2013/CIM-schema-cim16-info#"),
    "entsoe": Namespace("http://entsoe.eu/CIM/SchemaExtension/3/1#"),
    "entsoe2": Namespace("http://entsoe.eu/CIM/SchemaExtension/3/2#"),
    "md": Namespace("http://iec.ch/TC57/61970-552/ModelDescription/1#"),
    "pti": Namespace("http://www.pti-us.com/PTI_CIM-schema-cim16#"),
    "tnt": Namespace("http://purl.org/cognite/tnt#"),
    "neat": DEFAULT_NAMESPACE,
}


DEFAULT_URI = ""

DEFAULT_DOCS_URL = "https://cognite-neat.readthedocs-hosted.com/en/latest/"
