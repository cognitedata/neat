from typing import Literal, TypeAlias

MIMETypes: TypeAlias = Literal[
    "application/rdf+xml", "text/turtle", "application/n-triple", "application/n-quads", "application/trig"
]


def rdflib_to_mime_types(rdflib_format: str) -> str | None:
    """Convert an RDFlib format to a MIME type.

    Args:
        rdflib_format (str): The RDFlib format.

    Returns:
        MIMETypes: The MIME type.

    !!! note
        This will be replaced once new version of oxrdflib is released.

    """

    mapping = {
        "xml": "application/rdf+xml",
        "rdf": "application/rdf+xml",
        "owl": "application/rdf+xml",
        "n3": "application/n-triple",
        "ttl": "text/turtle",
        "turtle": "text/turtle",
        "nt": "application/n-triple",
        "nq": "application/n-quads",
        "nquads": "application/n-quads",
        "trig": "application/trig",
    }
    return mapping.get(rdflib_format, None)
