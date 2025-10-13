import pytest
from rdflib import RDF, Literal, Namespace

from cognite.neat import NeatSession
from cognite.neat.v0.core._constants import NAMED_GRAPH_NAMESPACE
from cognite.neat.v0.core._issues.errors import NeatValueError


def test_session_diff_instances(tmp_path) -> None:
    current_file = tmp_path / "current.ttl"
    current_file.write_text(
        """
        @prefix ex: <http://example.org/> .
        ex:instance1 a ex:Type1 .
        ex:instance1 ex:prop "v1" .
        ex:instance2 a ex:Type1 .
        ex:instance2 ex:prop "v2" .
    """
    )

    new_file = tmp_path / "new.ttl"
    new_file.write_text(
        """
        @prefix ex: <http://example.org/> .
        ex:instance1 a ex:Type1 .
        ex:instance1 ex:prop "v1_modified" .
        ex:instance3 a ex:Type2 .
        ex:instance3 ex:prop "v3" .
    """
    )

    neat = NeatSession()
    neat.read.rdf.instances(current_file, named_graph="CURRENT")
    neat.read.rdf.instances(new_file, named_graph="NEW")

    neat._diff.instances("CURRENT", "NEW")

    store = neat._state.instances.store
    add_graph = store.graph(NAMED_GRAPH_NAMESPACE["DIFF_ADD"])
    delete_graph = store.graph(NAMED_GRAPH_NAMESPACE["DIFF_DELETE"])

    ex = Namespace("http://example.org/")
    assert (ex.instance1, ex.prop, Literal("v1_modified")) in add_graph
    assert (ex.instance3, RDF.type, ex.Type2) in add_graph
    assert (ex.instance1, ex.prop, Literal("v1")) in delete_graph
    assert (ex.instance2, RDF.type, ex.Type1) in delete_graph


def test_session_diff_nonexistent_graph(tmp_path) -> None:
    current_file = tmp_path / "current.ttl"
    current_file.write_text(
        """
        @prefix ex: <http://example.org/> .
        ex:instance1 a ex:Type1 .
    """
    )

    neat = NeatSession()
    neat.read.rdf.instances(current_file, named_graph="CURRENT")

    with pytest.raises(NeatValueError):
        neat._diff.instances("CURRENT", "NONEXISTENT")
