from abc import ABC
from dataclasses import dataclass, field
from typing import Any

from cognite.neat._issues import IssueList
from cognite.neat._shared import NeatList, NeatObject


@dataclass
class GraphTransformationResult(NeatObject, ABC):
    name: str
    affected_nodes_count: int | None = None
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    issues: IssueList = field(default_factory=IssueList)

    def dump(self, aggregate: bool = True) -> dict[str, Any]:
        output: dict[str, Any] = {"name": self.name}
        if self.added:
            output["added"] = len(self.added) if aggregate else self.added
        if self.removed:
            output["removed"] = len(self.removed) if aggregate else self.removed
        if self.skipped:
            output["skipped"] = len(self.skipped) if aggregate else self.skipped
        if self.affected_nodes_count:
            output["affected nodes"] = self.affected_nodes_count
        if self.issues:
            output["issues"] = len(self.issues) if aggregate else [issue.dump() for issue in self.issues]
        return output


class GraphTransformationResultList(NeatList[GraphTransformationResult]):
    def _repr_html_(self) -> str:
        df = self.to_pandas().fillna(0)
        df = df.style.format({column: "{:,.0f}".format for column in df.select_dtypes(include="number").columns})
        return df._repr_html_()  # type: ignore[attr-defined]
