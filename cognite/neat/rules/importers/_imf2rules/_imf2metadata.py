import datetime
import re

from rdflib import Namespace

from cognite.neat.rules.models import RoleTypes, SchemaCompleteness
from cognite.neat.rules.models._types._base import (
    PREFIX_COMPLIANCE_REGEX,
    VERSION_COMPLIANCE_REGEX,
)
from cognite.neat.utils.utils import convert_rdflib_content


def parse_imf_metadata() -> dict:
    """Provide hardcoded IMF metadata to dict.

    Returns:
        Dictionary containing IMF metadata

    !!! note "Compliant IMF metadata"
        The current RDF provide IMF types as SHACL, but there are not any metadata describing
        the actual content.

    """

    raw_metadata = convert_rdflib_content(
        {
            "role": RoleTypes.information_architect,
            "schema": SchemaCompleteness.partial,
            "prefix": "imf",
            "namespace": Namespace("http://posccaesar.org/imf"),
            "version": None,
            "created": None,
            "updated": None,
            "title": "IMF - types",
            "description": "IMF - types",
            "creator": None,
            "rights": None,
            "license": None,
        }
    )

    return make_metadata_compliant(raw_metadata)


def make_metadata_compliant(metadata: dict) -> dict:
    """Attempts to fix errors in metadata, otherwise defaults to values that will pass validation.

    Args:
        metadata: Dictionary containing metadata

    Returns:
        Dictionary containing metadata with fixed errors
    """

    metadata = fix_namespace(metadata, default=Namespace("https://posccaesar.org/imf/"))
    metadata = fix_prefix(metadata, default="pca-imf")
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


def fix_prefix(metadata: dict, default: str) -> dict:
    if prefix := metadata.get("prefix", None):
        if not isinstance(prefix, str) or not re.match(PREFIX_COMPLIANCE_REGEX, prefix):
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
                return metadata
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
        if not re.match(VERSION_COMPLIANCE_REGEX, version):
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
