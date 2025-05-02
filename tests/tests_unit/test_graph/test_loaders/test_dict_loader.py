from collections.abc import Iterable
from pathlib import Path

import pyarrow.parquet as pq
from rdflib import RDF, Literal, Namespace

from cognite.neat._graph import extractors
from cognite.neat._graph.examples import nordic44_knowledge_graph
from cognite.neat._graph.loaders import DictLoader
from cognite.neat._shared import Triple
from cognite.neat._store import NeatGraphStore


class TestLocationFilterLoader:
    def test_write_parquet_table(self, tmp_path: Path) -> None:
        store = NeatGraphStore.from_oxi_local_store()

        class DummyExtractor:
            def extract(self) -> Iterable[Triple]:
                namespace = Namespace("http://example.org/")
                my_asset = namespace["my_asset"]
                yield my_asset, RDF.type, namespace["Asset"]
                yield my_asset, namespace["name"], Literal("Doctrino Asset")
                yield my_asset, namespace["description"], Literal("Doctrino Asset Description")
                yield my_asset, namespace["createdYear"], Literal(2025)
                yield my_asset, namespace["price"], Literal(1234.56)
                yield my_asset, namespace["isActive"], Literal(True)
                yield my_asset, namespace["path"], Literal(["root", "level1", "level2"])

        store.write(DummyExtractor())

        loader = DictLoader(store, "parquet")
        parquet_folder = tmp_path / "parquet_folder"
        parquet_folder.mkdir(parents=True, exist_ok=True)

        loader.write_to_file(parquet_folder)

        expected_asset_file = parquet_folder / "Asset.parquet"
        assert expected_asset_file.exists()
        table = pq.read_table(expected_asset_file)
        expected_content = [
            {
                "name": "Doctrino Asset",
                "description": "Doctrino Asset Description",
                "createdYear": 2025,
                "price": 1234.56,
                "isActive": True,
                "path": "['root', 'level1', 'level2']",
            }
        ]
        assert table.to_pylist() == expected_content

    def test_write_parquet_tables_nordic44(self, tmp_path: Path) -> None:
        store = NeatGraphStore.from_oxi_local_store()
        store.write(extractors.RdfFileExtractor(nordic44_knowledge_graph))

        loader = DictLoader(store, "parquet")

        parquet_folder = tmp_path / "parquet_folder"
        parquet_folder.mkdir(parents=True, exist_ok=True)

        loader.write_to_file(parquet_folder)

        expected_types = set(store.queries.select.list_types(remove_namespace=True))
        actual_types = {table.stem for table in parquet_folder.glob("*.parquet")}
        assert expected_types == actual_types
