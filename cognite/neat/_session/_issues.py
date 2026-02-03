import json
import uuid
from collections import defaultdict
from typing import Any

from cognite.neat._data_model._fix_actions import (
    AddConstraintAction,
    AddIndexAction,
    FixAction,
    RemoveConstraintAction,
)
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
    def _applied_fixes(self) -> list[FixAction]:
        """Get all applied fixes from the last change in the store."""
        if change := self._store.provenance.last_change:
            return change.applied_fixes or []
        return []

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
                    "fixed": False,
                }
            )
        return serialized

    @property
    def _serialized_applied_fixes(self) -> list[dict[str, Any]]:
        """Convert applied fixes to JSON-serializable format for the Fixed tab.

        Each fix is displayed individually, like issues. Subclass-specific fields
        are included for fancy UI rendering.
        """
        serialized = []
        for idx, fix_action in enumerate(self._applied_fixes):
            item: dict[str, Any] = {
                "id": f"fixed-{idx}",
                "type": "Fixed",
                "code": fix_action.code,
                "message": fix_action.message,
                "fix": "",
                "fixed": True,
            }

            # Add subclass-specific fields for fancy UI rendering
            if isinstance(fix_action, (AddConstraintAction, RemoveConstraintAction)):
                item["fix_type"] = "constraint"
                item["source_name"] = fix_action.source_name
                item["dest_name"] = fix_action.dest_name
                item["action_type"] = fix_action.action_type
                item["constraint_id"] = fix_action.constraint_id
            elif isinstance(fix_action, AddIndexAction):
                item["fix_type"] = "index"
                item["container_name"] = fix_action.container_name
                item["property_id"] = fix_action.property_id
                item["index_id"] = fix_action.index_id

            serialized.append(item)
        return serialized

    def _repr_html_(self) -> str:
        """Generate interactive HTML representation."""
        has_issues = len(self._issues) > 0
        has_fixed = len(self._applied_fixes) > 0

        if not has_issues and not has_fixed:
            return "<b>No issues found.</b>"

        stats = self._stats

        # Generate unique ID for this render to avoid conflicts in Jupyter
        unique_id = uuid.uuid4().hex[:8]

        # Combine current issues and applied fixes for the JSON data
        all_serialized = self._serialized_issues + self._serialized_applied_fixes

        template_vars = {
            "JSON": json.dumps(all_serialized),
            "total": stats["total"],
            "syntax_errors": stats["by_type"].get("ModelSyntaxError", 0),
            "consistency_errors": stats["by_type"].get("ConsistencyError", 0),
            "recommendations": stats["by_type"].get("Recommendation", 0),
            "fixed_count": len(self._applied_fixes),
            "unique_id": unique_id,
        }

        return render("issues", template_vars)
