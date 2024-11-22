from typing import Literal, TypeAlias

MIMETypes: TypeAlias = Literal[
    "application/rdf+xml", "text/turtle", "application/n-triple", "application/n-quads", "application/trig"
]

RDFTypes: TypeAlias = Literal["xml", "rdf", "owl", "n3", "ttl", "turtle", "nt", "nq", "nquads", "trig"]


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


def mime_to_oxi_types(mime_type: str) -> str | None:
    """Convert an MIME type to OXI type.

    Args:
        mime_type (str): The MIME type.

    Returns:
        MIMETypes: The MIME type.

    !!! note
        This will be replaced once new version of oxrdflib is released.

    """

    mapping = {
        "application/rdf+xml": "ox-xml",
        "application/n-triple": "ox-nt",
        "text/turtle": "ox-turtle",
        "application/n-quads": "ox-nquads",
        "application/trig": "ox-trig",
    }

    return mapping.get(mime_type, None)


def rdflib_to_oxi_types(rdflib_format: str) -> str | None:
    """Convert an RDFlib format to a MIME type.

    Args:
        rdflib_format (str): The RDFlib format.

    Returns:
        MIMETypes: The MIME type.

    !!! note
        This will be replaced once new version of oxrdflib is released.

    """

    mapping = {
        "xml": "ox-xml",
        "rdf": "ox-xml",
        "owl": "ox-xml",
        "n3": "ox-n3",
        "ttl": "ox-ttl",
        "turtle": "ox-turtle",
        "nt": "ox-nt",
        "nq": "ox-nq",
        "nquads": "ox-nquads",
        "trig": "ox-trig",
    }
    return mapping.get(rdflib_format, None)
