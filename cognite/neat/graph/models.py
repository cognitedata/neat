from typing import TypeAlias

from rdflib import Literal
from rdflib.term import URIRef

Triple: TypeAlias = tuple[URIRef, URIRef, Literal | URIRef]
InstanceType: TypeAlias = URIRef
