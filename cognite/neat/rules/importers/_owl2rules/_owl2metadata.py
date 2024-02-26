import datetime
import re

from rdflib import Graph, Namespace

from cognite.neat.rules.models._rules.base import RoleTypes, SchemaCompleteness
from cognite.neat.rules.models.rules import (
    prefix_compliance_regex,
    version_compliance_regex,
)
from cognite.neat.utils.utils import convert_rdflib_content, remove_none_elements_from_set


def parse_owl_metadata(graph: Graph, make_compliant: bool = False) -> dict:
    """Parse owl metadata from graph to dict.

    Args:
        graph: Graph containing owl metadata
        make_compliant: Flag for generating compliant metadata, by default False

    Returns:
        Dictionary containing owl metadata

    !!! note "make_compliant"
        If `make_compliant` is set to True, in presence of errors, default values will be used instead.
        This makes the method very opinionated, but results in a compliant metadata.


    """
    # TODO: Move dataframe to dict representation

    query = """SELECT ?namespace ?prefix ?version ?created ?updated ?title ?description ?creator ?rights ?license
    WHERE {
        ?namespace a owl:Ontology .
        OPTIONAL {?namespace owl:versionInfo ?version }.
        OPTIONAL {?namespace dcterms:creator ?creator }.
        OPTIONAL {?namespace dcterms:title|rdfs:label|skos:prefLabel ?title }.
        OPTIONAL {?namespace dcterms:modified ?updated }.
        OPTIONAL {?namespace dcterms:created ?created }.
        OPTIONAL {?namespace dcterms:description ?description }.

        OPTIONAL {?namespace dcterms:rights|dc:rights ?rights }.

        OPTIONAL {?namespace dcterms:license|dc:license ?license }.
        FILTER (!isBlank(?namespace))
        FILTER (!bound(?description) || LANG(?description) = "" || LANGMATCHES(LANG(?description), "en"))
        FILTER (!bound(?title) || LANG(?title) = "" || LANGMATCHES(LANG(?title), "en"))
    }
    """

    results = [{item for item in sublist} for sublist in list(zip(*graph.query(query), strict=True))]

    raw_metadata = convert_rdflib_content(
        {
            "role": RoleTypes.information_architect,
            "schema": SchemaCompleteness.partial,
            "prefix": results[1].pop(),
            "namespace": Namespace(results[0].pop()),
            "version": results[2].pop(),
            "created": results[3].pop(),
            "updated": results[4].pop(),
            "title": results[5].pop(),
            "description": results[6].pop(),
            "creator": (
                ", ".join(remove_none_elements_from_set(results[7]))
                if remove_none_elements_from_set(results[7])
                else None
            ),
            "rights": results[8].pop(),
            "license": results[9].pop(),
        }
    )

    if make_compliant:
        raw_metadata.pop("created")
        return make_metadata_compliant(raw_metadata)

    return raw_metadata


def make_metadata_compliant(metadata: dict) -> dict:
    """Attempts to fix errors in metadata, otherwise defaults to values that will pass validation.

    Args:
        metadata: Dictionary containing metadata

    Returns:
        Dictionary containing metadata with fixed errors
    """

    metadata = fix_namespace(metadata, default=Namespace("http://purl.org/cognite/neat#"))
    metadata = fix_prefix(metadata)
    metadata = fix_version(metadata)
    metadata = fix_date(metadata, date_type="created", default=datetime.datetime.now().replace(microsecond=0))
    metadata = fix_date(metadata, date_type="updated", default=datetime.datetime.now().replace(microsecond=0))
    metadata = fix_title(metadata)
    metadata = fix_description(metadata)
    metadata = fix_author(metadata, "creator")
    metadata = fix_rights(metadata)
    metadata = fix_license(metadata)

    return metadata


def fix_license(metadata: dict, default: str = "Unknown license") -> dict:
    if license := metadata.get("license", None):
        if not isinstance(license, str):
            metadata["license"] = default
        elif isinstance(license, str) and len(license) == 0:
            metadata["license"] = default
    else:
        metadata["license"] = default
    return metadata


def fix_rights(metadata: dict, default: str = "Unknown rights") -> dict:
    if rights := metadata.get("rights", None):
        if not isinstance(rights, str):
            metadata["rights"] = default
        elif isinstance(rights, str) and len(rights) == 0:
            metadata["rights"] = default
    else:
        metadata["rights"] = default
    return metadata


def fix_author(metadata: dict, author_type: str = "creator", default: str = "NEAT") -> dict:
    if author := metadata.get(author_type, None):
        if not isinstance(author, str) or isinstance(author, list):
            metadata[author_type] = default
        elif isinstance(author, str) and len(author) == 0:
            metadata[author_type] = default
    else:
        metadata[author_type] = default
    return metadata


def fix_description(metadata: dict, default: str = "This model has been inferred from OWL ontology") -> dict:
    if description := metadata.get("description", None):
        if not isinstance(description, str) or len(description) == 0:
            metadata["description"] = default
        elif isinstance(description, str) and len(description) > 1024:
            metadata["description"] = metadata["description"][:1024]
    else:
        metadata["description"] = default
    return metadata


def fix_prefix(metadata: dict, default: str = "neat") -> dict:
    if prefix := metadata.get("prefix", None):
        if not isinstance(prefix, str) or not re.match(prefix_compliance_regex, prefix):
            metadata["prefix"] = default
    else:
        metadata["prefix"] = default
    return metadata


def fix_namespace(metadata: dict, default: Namespace) -> dict:
    if namespace := metadata.get("namespace", None):
        if not isinstance(namespace, Namespace):
            try:
                metadata["namespace"] = Namespace(namespace)
            except Exception:
                metadata["namespace"] = default
    else:
        metadata["namespace"] = default

    return metadata


def fix_date(
    metadata: dict,
    date_type: str,
    default: datetime.datetime,
) -> dict:
    if date := metadata.get(date_type, None):
        try:
            if isinstance(date, datetime.datetime):
                pass
            elif isinstance(date, datetime.date):
                metadata[date_type] = datetime.datetime.combine(metadata[date_type], datetime.datetime.min.time())
            elif isinstance(date, str):
                metadata[date_type] = datetime.datetime.strptime(metadata[date_type], "%Y-%m-%dT%H:%M:%SZ")
            else:
                metadata[date_type] = default
        except Exception:
            metadata[date_type] = default
    else:
        metadata[date_type] = default

    return metadata


def fix_version(metadata: dict, default: str = "1.0.0") -> dict:
    if version := metadata.get("version", None):
        if not re.match(version_compliance_regex, version):
            metadata["version"] = default
    else:
        metadata["version"] = default

    return metadata


def fix_title(metadata: dict, default: str = "OWL Inferred Data Model") -> dict:
    if title := metadata.get("title", None):
        if not isinstance(title, str):
            metadata["title"] = default
        elif isinstance(title, str) and len(title) == 0:
            metadata["title"] = default
        elif isinstance(title, str) and len(title) > 255:
            metadata["title"] = metadata["title"][:255]
        else:
            pass
    else:
        metadata["title"] = default

    return metadata
