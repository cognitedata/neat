from rdflib import Namespace

from cognite.neat._rules.importers._rdf._shared import make_metadata_compliant
from cognite.neat._rules.models import RoleTypes, SchemaCompleteness


def parse_imf_metadata(prefix: str = "pcaimf") -> dict:
    """Provide hardcoded IMF metadata to dict.

    Returns:
        Dictionary containing IMF metadata

    !!! note "Compliant IMF metadata"
        The current RDF provide IMF types as SHACL, but there are not any metadata describing
        the actual content.

    """

    raw_metadata = {
        "role": RoleTypes.information,
        "schema": SchemaCompleteness.partial,
        "prefix": prefix,
        "namespace": Namespace("https://posccaesar.org/imf/"),
        "version": None,
        "created": None,
        "updated": None,
        "title": "IMF_types",
        "description": "IMF - types",
        "creator": None,
        "rights": None,
        "license": None,
    }

    return make_metadata_compliant(raw_metadata)
