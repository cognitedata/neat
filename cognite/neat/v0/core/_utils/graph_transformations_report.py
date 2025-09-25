from abc import ABC
from dataclasses import dataclass
from typing import Any

from cognite.neat.v0.core._shared import NeatList, NeatObject


@dataclass
class GraphTransformationResult(NeatObject, ABC):
    name: str
    affected_nodes_count: int | None = None
    added: int | None = None
    removed: int | None = None
    skipped: int | None = None
    modified: int | None = None

    def dump(self, aggregate: bool = True) -> dict[str, Any]:
        output: dict[str, Any] = {"name": self.name}
        if self.added:
            output["added"] = self.added
        if self.removed:
            output["removed"] = self.removed
        if self.skipped:
            output["skipped"] = self.skipped
        if self.affected_nodes_count:
            output["affected nodes"] = self.affected_nodes_count
        if self.modified:
            output["modified instances"] = self.modified
        return output


class GraphTransformationResultList(NeatList[GraphTransformationResult]):
    def _repr_html_(self) -> str:
        df = self.to_pandas().fillna(0)
        df = df.style.format({column: "{:,.0f}".format for column in df.select_dtypes(include="number").columns})
        return df._repr_html_()  # type: ignore[attr-defined]
