from typing import TypeAlias

from rdflib import RDF, Literal
from rdflib.term import URIRef

Triple: TypeAlias = tuple[URIRef, URIRef, Literal | URIRef]
InstanceType = RDF.type
