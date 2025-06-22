import string
from collections import deque
from collections.abc import Callable, Iterable

import pytest
from cognite_toolkit._cdf_tk.utils.tarjan import tarjan
from hypothesis import given
from hypothesis import strategies as st


def tarjan_test_cases() -> Iterable:
    yield pytest.param(
        {},
        [],
        id="Empty graph",
    )
    yield pytest.param(
        {"A": set()},
        [{"A"}],
        id="Single node",
    )
    yield pytest.param(
        {"A": {"B"}, "B": set()},
        [{"B"}, {"A"}],
        id="Two nodes",
    )
    yield pytest.param(
        {"A": {"B"}, "B": {"A"}},
        [{"A", "B"}],
        id="Circular dependency",
    )
    yield pytest.param(
        {"A": {"B"}, "B": {"C"}, "C": {"A"}},
        [{"C", "B", "A"}],
        id="Circular dependency with three nodes",
    )
    yield pytest.param(
        {"A": {"A"}},
        [{"A"}],
        id="Self loop",
    )
    yield pytest.param(
        {"A": {"B"}, "B": {"C"}, "C": {"A"}, "D": {"D"}},
        [{"C", "B", "A"}, {"D"}],
        id="Cycle and self loop",
    )
    yield pytest.param(
        {"A": {"B"}, "B": {"C"}, "C": {"D"}, "D": {"B"}},
        [{"D", "C", "B"}, {"A"}],
        id="Chain into cycle",
    )


@st.composite
def random_graph(draw: Callable) -> dict[str, set[str]]:
    nodes = draw(
        st.lists(st.text(string.ascii_uppercase, min_size=1, max_size=2), min_size=2, max_size=15, unique=True)
    )
    graph: dict[str, set[str]] = {}
    for node in nodes:
        # Limit out-degree to at most len(nodes) - 1
        possible_neighbors = [n for n in nodes if n != node]
        neighbors = set(
            draw(
                st.lists(st.sampled_from(possible_neighbors), min_size=0, max_size=len(possible_neighbors), unique=True)
            )
        )
        graph[node] = neighbors
    return graph


def is_reachable(graph: dict[str, set[str]], start: str, end: str) -> bool:
    visited = set()
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == end:
            return True
        for neighbor in graph.get(node, set()):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append(neighbor)
    return False


class TestTarjan:
    @pytest.mark.parametrize("graph, expected", tarjan_test_cases())
    def test_tarjan(self, graph: dict[str, set[str]], expected: list[set[str]]):
        result = tarjan(graph)
        assert result == expected

    @given(graph=random_graph())
    def test_tarjan_scc_mutual_reachability(self, graph: dict[str, set[str]]) -> None:
        sccs = tarjan(graph)
        node_to_scc: dict[str, set[str]] = {}
        for scc in sccs:
            for node in scc:
                node_to_scc[node] = scc

        nodes = list(graph.keys())
        for a in nodes:
            for b in nodes:
                are_mutually_reachable = is_reachable(graph, a, b) and is_reachable(graph, b, a)
                is_same_strongly_connected_components = node_to_scc.get(a) == node_to_scc.get(b)
                assert are_mutually_reachable == is_same_strongly_connected_components
