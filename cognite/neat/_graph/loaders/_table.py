import typing
from collections.abc import Iterable
from pathlib import Path

from cognite.neat._issues import NeatIssue
from cognite.neat._store import NeatGraphStore

from ._base import _END_OF_CLASS, _START_OF_CLASS, BaseLoader


class DictLoader(BaseLoader[dict[str, object]]):
    def __init__(self, graph_store: NeatGraphStore, file_format: typing.Literal["parquet"] = "parquet") -> None:
        self.graph_store = graph_store
        if file_format != "parquet":
            raise ValueError(f"Unsupported file format: {file_format!r}. Only 'parquet' is supported.")
        self.file_format = file_format

    def write_to_file(self, filepath: Path) -> None:
        raise NotImplementedError()

    def _load(
        self, stop_on_exception: bool = False
    ) -> Iterable[dict[str, object] | NeatIssue | type[_END_OF_CLASS] | _START_OF_CLASS]:
        raise NotImplementedError()
