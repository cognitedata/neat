from cognite.neat._rules.importers._rdf._shared import make_metadata_compliant
from cognite.neat._rules.models import RoleTypes


def parse_imf_metadata(space: str = "pcaimf") -> dict:
    """Provide hardcoded IMF metadata to dict.

    Returns:
        Dictionary containing IMF metadata

    !!! note "Compliant IMF metadata"
        The current RDF provide IMF types as SHACL, but there are not any metadata describing
        the actual content.

    """

    raw_metadata = {
        "role": RoleTypes.information,
        "space": space,
        "external_id": "imf_types",
        "version": None,
        "created": None,
        "updated": None,
        "name": "IMF Types",
        "description": "IMF - types",
        "creator": None,
    }

    return make_metadata_compliant(raw_metadata)
