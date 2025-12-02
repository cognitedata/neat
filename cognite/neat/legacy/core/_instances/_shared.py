from typing import Literal, TypeAlias

MIMETypes: TypeAlias = Literal[
    "application/rdf+xml", "text/turtle", "application/n-triple", "application/n-quads", "application/trig"
]

RDFTypes: TypeAlias = Literal["xml", "rdf", "owl", "n3", "ttl", "turtle", "nt", "nq", "nquads", "trig"]


def quad_formats() -> list[str]:
    return ["trig", "nquads", "nq", "nt"]


def rdflib_to_oxi_type(rdflib_format: str) -> str | None:
    """Convert an RDFlib format to a MIME type.

    Args:
        rdflib_format (str): The RDFlib format.

    Returns:
        Oxi format used to trigger correct plugging in rdflib

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
