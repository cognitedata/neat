from collections.abc import Iterable
from pathlib import Path

from cognite.neat._issues import NeatIssue

from ._base import _END_OF_CLASS, _START_OF_CLASS, BaseLoader


class DictLoader(BaseLoader[dict[str, object]]):
    def write_to_file(self, filepath: Path) -> None:
        raise NotImplementedError()

    def _load(
        self, stop_on_exception: bool = False
    ) -> Iterable[dict[str, object] | NeatIssue | type[_END_OF_CLASS] | _START_OF_CLASS]:
        raise NotImplementedError()
