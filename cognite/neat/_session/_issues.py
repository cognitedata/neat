import json
from collections import defaultdict
from typing import Any

from cognite.neat._issues import ConsistencyError, IssueList, ModelSyntaxError, Recommendation
from cognite.neat._session._html._render import render
from cognite.neat._store import NeatStore


class Issues:
    """Class to handle issues in the NeatSession."""

    def __init__(self, store: NeatStore) -> None:
        self._store = store

    @property
    def _issues(self) -> IssueList:
        """Get all issues from the last change in the store."""
        issues = IssueList()
        if change := self._store.provenance.last_change:
            issues += change.errors or IssueList()
            issues += change.issues or IssueList()
        return issues

    @property
    def _stats(self) -> dict[str, Any]:
        """Compute statistics about issues."""
        by_type: defaultdict[str, int] = defaultdict(int)
        by_code: defaultdict[str, int] = defaultdict(int)

        stats: dict[str, Any] = {
            "total": len(self._issues),
            "by_type": by_type,
            "by_code": by_code,
            "severity_order": [ModelSyntaxError.__name__, ConsistencyError.__name__, Recommendation.__name__],
        }

        for issue in self._issues:
            stats["by_type"][issue.issue_type()] += 1

            if issue.code:
                stats["by_code"][f"{issue.issue_type()}:{issue.code}"] += 1

        return stats

    @property
    def _serialized_issues(self) -> list[dict[str, Any]]:
        """Convert issues to JSON-serializable format."""
        serialized = []
        for idx, issue in enumerate(self._issues):
            serialized.append(
                {
                    "id": idx,
                    "type": issue.issue_type(),
                    "code": issue.code or "",
                    "message": issue.message,
                    "fix": issue.fix or "",
                }
            )
        return serialized

    def _repr_html_(self) -> str:
        """Generate interactive HTML representation."""
        if not self._issues:
            return "<b>No issues found.</b>"
        stats = self._stats

        template_vars = {
            "JSON": json.dumps(self._serialized_issues),
            "total": stats["total"],
            "syntax_errors": stats["by_type"].get("ModelSyntaxError", 0),
            "consistency_errors": stats["by_type"].get("ConsistencyError", 0),
            "recommendations": stats["by_type"].get("Recommendation", 0),
        }

        return render("issues", template_vars)
