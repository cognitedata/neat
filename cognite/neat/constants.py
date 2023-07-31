from pathlib import Path
from rdflib import Namespace
from cognite import neat


PACKAGE_DIRECTORY = Path(neat.__file__).parent


EXAMPLE_RULES = PACKAGE_DIRECTORY / "rules" / "examples"
EXAMPLE_GRAPHS = PACKAGE_DIRECTORY / "graph" / "examples"
EXAMPLE_WORKFLOWS = PACKAGE_DIRECTORY / "workflows" / "examples"


PREFIXES = {
    # "rdf": Namespace("http://www.w3.org/1999/02/22-rdf-syntax-ns#"), # noqa
    # "rdfs": Namespace("http://www.w3.org/2000/01/rdf-schema#"),# noqa
    # "owl": Namespace("http://www.w3.org/2002/07/owl#"),# noqa
    # "sh": Namespace("http://www.w3.org/ns/shacl#"),
    "dct": Namespace("http://purl.org/dc/terms/"),
    "skos": Namespace("http://www.w3.org/2004/02/skos/core#"),
    "pav": Namespace("http://purl.org/pav/"),
    "cim": Namespace("http://iec.ch/TC57/2013/CIM-schema-cim16#"),
    "icim": Namespace("http://iec.ch/TC57/2013/CIM-schema-cim16-info#"),
    "entsoe": Namespace("http://entsoe.eu/CIM/SchemaExtension/3/1#"),
    "entsoe2": Namespace("http://entsoe.eu/CIM/SchemaExtension/3/2#"),
    "md": Namespace("http://iec.ch/TC57/61970-552/ModelDescription/1#"),
    "pti": Namespace("http://www.pti-us.com/PTI_CIM-schema-cim16#"),
    "tnt": Namespace("http://purl.org/cognite/tnt#"),
    "neat": Namespace("http://purl.org/cognite/neat#"),
}

DEFAULT_NAMESPACE = Namespace("http://purl.org/cognite/app#")
DEFAULT_URI = ""
