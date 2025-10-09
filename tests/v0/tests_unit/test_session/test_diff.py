import pytest

from cognite.neat import NeatSession
from cognite.neat.v0.core._constants import NAMED_GRAPH_NAMESPACE
from cognite.neat.v0.core._issues.errors import NeatValueError


def test_session_diff_instances(tmp_path) -> None:
    old_file = tmp_path / "old.ttl"
    old_file.write_text(
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
    neat.read.rdf.instances(old_file, named_graph="OLD")
    neat.read.rdf.instances(new_file, named_graph="NEW")

    neat._diff.instances("OLD", "NEW")

    store = neat._state.instances.store
    assert NAMED_GRAPH_NAMESPACE["DIFF_ADD"] in store.named_graphs
    assert NAMED_GRAPH_NAMESPACE["DIFF_DELETE"] in store.named_graphs


def test_session_diff_nonexistent_graph(tmp_path) -> None:
    old_file = tmp_path / "old.ttl"
    old_file.write_text(
        """
        @prefix ex: <http://example.org/> .
        ex:instance1 a ex:Type1 .
    """
    )

    neat = NeatSession()
    neat.read.rdf.instances(old_file, named_graph="OLD")

    with pytest.raises(NeatValueError):
        neat._diff.instances("OLD", "NONEXISTENT")
