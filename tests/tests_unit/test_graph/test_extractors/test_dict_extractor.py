from rdflib import Literal, Namespace

from cognite.neat._graph.extractors import DictExtractor
from cognite.neat._graph.extractors._dict import DEFAULT_EMPTY_VALUES, IGNORED_BY_TRIPLE_STORE
from cognite.neat._store import NeatGraphStore


class TestDictExtractor:
    def test_extract_with_empty_values(self) -> None:
        namespace = Namespace("http://example.org/")
        id_ = namespace["my_instance"]
        extractor = DictExtractor(
            id_=id_,
            data={
                "myProperty": "value",
                **{f"myEmptyProperty{no}": Literal(value) for no, value in enumerate(sorted(DEFAULT_EMPTY_VALUES))},
            },
            namespace=namespace,
            empty_values=set(),
        )

        store = NeatGraphStore.from_oxi_local_store()
        store.write(extractor)

        _, properties = store.queries.select.describe(id_)

        assert dict(properties) == {
            "myProperty": ["value"],
            **{
                f"myEmptyProperty{no}": ["EMPTY"] if value in IGNORED_BY_TRIPLE_STORE else [value]
                for no, value in enumerate(sorted(DEFAULT_EMPTY_VALUES))
            },
        }
