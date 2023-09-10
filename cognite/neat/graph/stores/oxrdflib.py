import shutil
from collections.abc import Generator, Iterable, Iterator, Mapping
from typing import Any, cast

import pyoxigraph as ox
from rdflib import Graph
from rdflib.graph import DATASET_DEFAULT_GRAPH_ID
from rdflib.plugins.sparql.sparql import Query, Update
from rdflib.query import Result
from rdflib.store import VALID_STORE, Store
from rdflib.term import BNode, Identifier, Literal, Node, URIRef, Variable

__all__ = ["OxigraphStore"]

from typing import TypeAlias

_Triple: TypeAlias = tuple[Node, Node, Node]
_Quad: TypeAlias = tuple[Node, Node, Node, Graph]
_TriplePattern: TypeAlias = tuple[Node | None, Node | None, Node | None]


class OxigraphStore(Store):
    context_aware: bool = True
    formula_aware: bool = False
    transaction_aware: bool = False
    graph_aware: bool = True

    def __init__(
        self, configuration: str | None = None, identifier: Identifier | None = None, *, store: ox.Store | None = None
    ):
        self._store = store
        self._prefix_for_namespace: dict[URIRef, str] = {}
        self._namespace_for_prefix: dict[str, URIRef] = {}
        super().__init__(configuration, identifier)

    def open(self, configuration: str, create: bool = False) -> int | None:
        if self._store is not None:
            raise ValueError("The open function should be called before any RDF operation")
        self._store = ox.Store(configuration)
        return VALID_STORE

    def close(self, commit_pending_transaction: bool = False) -> None:
        del self._store

    def destroy(self, configuration: str) -> None:
        shutil.rmtree(configuration)

    def gc(self) -> None:
        pass

    @property
    def _inner(self) -> ox.Store:
        if self._store is None:
            self._store = ox.Store()
        return self._store

    def add(self, triple: _Triple, context: Graph, quoted: bool = False) -> None:
        if quoted:
            raise ValueError("Oxigraph stores are not formula aware")
        self._inner.add(_to_ox(triple, context))
        super().add(triple, context, quoted)

    def addN(self, quads: Iterable[_Quad]) -> None:
        self._inner.extend([_to_ox(q) for q in quads])
        for quad in quads:
            (s, p, o, g) = quad
            super().add((s, p, o), g)

    def remove(self, triple: _TriplePattern, context: Graph | None = None) -> None:
        for q in self._inner.quads_for_pattern(*_to_ox_quad_pattern(triple, context)):
            self._inner.remove(q)
        super().remove(triple, context)

    def triples(
        self, triple_pattern: _TriplePattern, context: Graph | None = None
    ) -> Iterator[tuple[_Triple, Iterator[Graph | None]]]:
        return (_from_ox(q) for q in self._inner.quads_for_pattern(*_to_ox_quad_pattern(triple_pattern, context)))

    def __len__(self, context: Graph | None = None) -> int:
        if context is None:
            # TODO: very bad
            return len({q.triple for q in self._inner})
        return sum(1 for _ in self._inner.quads_for_pattern(None, None, None, _to_ox(context)))

    def contexts(self, triple: _Triple | None = None) -> Generator[Graph, None, None]:
        if triple is None:
            return (_from_ox(g) for g in self._inner.named_graphs())
        return (_from_ox(q[3]) for q in self._inner.quads_for_pattern(*_to_ox_quad_pattern(triple)))

    def query(
        self,
        query: Query | str,
        initNs: Mapping[str, Any],
        initBindings: Mapping[str, Identifier],
        queryGraph: str,
        **kwargs: Any,
    ) -> "Result":
        if isinstance(queryGraph, Query) or kwargs:
            raise NotImplementedError
        init_ns = dict(self._namespace_for_prefix, **initNs)
        if isinstance(query, Query):
            query = str(query)
        query = "".join(f"PREFIX {prefix}: <{namespace}>\n" for prefix, namespace in init_ns.items()) + query
        if initBindings:
            # Todo Anders: This is likely a bug as .n3 is not valid the Identifier.
            #  There are no tests reaching this code.
            query += "\nVALUES ( {} ) {{ ({}) }}".format(
                " ".join(f"?{k}" for k in initBindings),
                " ".join(v.n3() for v in initBindings.values()),  # type: ignore[attr-defined]
            )
        result = self._inner.query(
            query,
            use_default_graph_as_union=queryGraph == "__UNION__",
            default_graph=_to_ox(queryGraph) if isinstance(queryGraph, Node) else None,
        )
        if isinstance(result, bool):
            out = Result("ASK")
            out.askAnswer = result
        elif isinstance(result, ox.QuerySolutions):
            out = Result("SELECT")
            out.vars = [Variable(v.value) for v in result.variables]
            out.bindings = [
                {v: _from_ox(val) for v, val in zip(out.vars, solution, strict=False)} for solution in result
            ]
        elif isinstance(result, ox.QueryTriples):
            out = Result("CONSTRUCT")
            out.graph = Graph()
            out.graph += (_from_ox(t) for t in result)
        else:
            raise ValueError(f"Unexpected query result: {result}")
        return out

    def update(
        self,
        update: Update | str,
        initNs: Mapping[str, Any],
        initBindings: Mapping[str, Identifier],
        queryGraph: str,
        **kwargs: Any,
    ) -> None:
        raise NotImplementedError

    def commit(self) -> None:
        # TODO: implement
        pass

    def rollback(self) -> None:
        # TODO: implement
        pass

    def add_graph(self, graph: Graph) -> None:
        self._inner.add_graph(_to_ox(graph))

    def remove_graph(self, graph: Graph) -> None:
        self._inner.remove_graph(_to_ox(graph))

    def bind(self, prefix: str, namespace: URIRef, override: bool = True) -> None:
        if not override and (prefix in self._namespace_for_prefix or namespace in self._prefix_for_namespace):
            return  # nothing to do
        self._delete_from_prefix(prefix)
        self._delete_from_namespace(namespace)
        self._namespace_for_prefix[prefix] = namespace
        self._prefix_for_namespace[namespace] = prefix

    def _delete_from_prefix(self, prefix):
        if prefix not in self._namespace_for_prefix:
            return
        namespace = self._namespace_for_prefix[prefix]
        del self._namespace_for_prefix[prefix]
        self._delete_from_namespace(namespace)

    def _delete_from_namespace(self, namespace):
        if namespace not in self._prefix_for_namespace:
            return
        prefix = self._prefix_for_namespace[namespace]
        del self._prefix_for_namespace[namespace]
        self._delete_from_prefix(prefix)

    def prefix(self, namespace: URIRef) -> str | None:
        return self._prefix_for_namespace.get(namespace)

    def namespace(self, prefix: str) -> URIRef | None:
        return self._namespace_for_prefix.get(prefix)

    def namespaces(self) -> Iterator[tuple[str, URIRef]]:
        yield from self._namespace_for_prefix.items()


def _to_ox(term: Node | _Triple | _Quad | Graph, context: Graph | None = None):
    if term is None:
        return None
    elif term == DATASET_DEFAULT_GRAPH_ID:
        return ox.DefaultGraph()
    elif isinstance(term, URIRef):
        return ox.NamedNode(term)
    elif isinstance(term, BNode):
        return ox.BlankNode(term)
    elif isinstance(term, Literal):
        return ox.Literal(term, language=term.language, datatype=ox.NamedNode(term.datatype) if term.datatype else None)
    elif isinstance(term, Graph):
        return _to_ox(term.identifier)
    elif isinstance(term, tuple) and len(term) == 3 and isinstance(context, Graph):
        triple = cast(_Triple, term)
        return ox.Quad(_to_ox(triple[0]), _to_ox(triple[1]), _to_ox(triple[2]), _to_ox(context))
    elif isinstance(term, tuple) and len(term) == 4:
        quad = cast(_Quad, term)
        return ox.Quad(_to_ox(quad[0]), _to_ox(quad[1]), _to_ox(quad[2]), _to_ox(quad[3]))
    raise ValueError(f"Unexpected rdflib term: {term!r}")


def _to_ox_quad_pattern(triple: _TriplePattern, context: Graph | None = None):
    (s, p, o) = triple
    return _to_ox_term_pattern(s), _to_ox_term_pattern(p), _to_ox_term_pattern(o), _to_ox_term_pattern(context)


def _to_ox_term_pattern(term):
    if term is None:
        return None
    if isinstance(term, URIRef):
        return ox.NamedNode(term)
    elif isinstance(term, BNode):
        return ox.BlankNode(term)
    elif isinstance(term, Literal):
        return ox.Literal(term, language=term.language, datatype=ox.NamedNode(term.datatype) if term.datatype else None)
    elif isinstance(term, Graph):
        return _to_ox(term.identifier)
    raise ValueError(f"Unexpected rdflib term: {term!r}")


def _from_ox(term):
    if term is None:
        return None
    if isinstance(term, ox.NamedNode):
        return URIRef(term.value)
    if isinstance(term, ox.BlankNode):
        return BNode(term.value)
    if isinstance(term, ox.Literal):
        if term.language:
            return Literal(term.value, lang=term.language)
        return Literal(term.value, datatype=URIRef(term.datatype.value))
    if isinstance(term, ox.DefaultGraph):
        return None
    if isinstance(term, ox.Triple):
        return _from_ox(term.subject), _from_ox(term.predicate), _from_ox(term.object)
    if isinstance(term, ox.Quad):
        return (_from_ox(term.subject), _from_ox(term.predicate), _from_ox(term.object)), _from_ox(term.graph_name)
    raise ValueError(f"Unexpected Oxigraph term: {term!r}")
