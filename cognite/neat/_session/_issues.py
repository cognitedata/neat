import json
import uuid
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from cognite.neat._issues import ConsistencyError, IssueList, ModelSyntaxError, Recommendation
from cognite.neat._session._html._render import render
from cognite.neat._store import NeatStore

if TYPE_CHECKING:
    from cognite.neat._data_model.rules._fix_actions import FixAction


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
    def _applied_fixes(self) -> list["FixAction"]:
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

    def _extract_relationship(self, fix_action: "FixAction") -> tuple[str, str] | None:
        """Extract source and destination from a fix action's target_ref and fix_id.

        Returns a tuple of (source_name, dest_name) or None if not a relationship fix.
        """
        # Parse the fix_id which has format like "CODE:action:space:src->space:dst"
        fix_id = fix_action.fix_id
        if "->" in fix_id:
            # Extract the arrow part: "space:src->space:dst"
            arrow_part = fix_id.split(":")[-1]  # Get last part after splitting
            # Actually the format is more like "CODE:add:space:Source->space:Dest"
            # Let's find the arrow and extract around it
            arrow_idx = fix_id.find("->")
            if arrow_idx != -1:
                # Find the last colon before arrow for source
                before_arrow = fix_id[:arrow_idx]
                after_arrow = fix_id[arrow_idx + 2 :]

                # Source is after the last colon before arrow
                src_parts = before_arrow.rsplit(":", 1)
                src_name = src_parts[-1] if src_parts else before_arrow

                # Dest might have "space:" prefix
                dst_parts = after_arrow.split(":", 1)
                dst_name = dst_parts[-1] if len(dst_parts) > 1 else after_arrow

                return (src_name, dst_name)
        return None

    @property
    def _serialized_applied_fixes(self) -> list[dict[str, Any]]:
        """Convert applied fixes to JSON-serializable format for the Fixed tab.

        Groups fixes by their generic message and provides structured data for
        a summary-style display.
        """
        # Group fixes by their generic message
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for fix_action in self._applied_fixes:
            relationship = self._extract_relationship(fix_action)
            item = {
                "description": fix_action.description,
                "source": relationship[0] if relationship else None,
                "dest": relationship[1] if relationship else None,
            }
            grouped[fix_action.message].append(item)

        # Convert to serialized format - one entry per group
        serialized = []
        for idx, (message, items) in enumerate(grouped.items()):
            # Extract code from first item's fix_id if available
            first_fix = self._applied_fixes[0] if self._applied_fixes else None
            code = first_fix.fix_id.split(":")[0] if first_fix and ":" in first_fix.fix_id else ""

            serialized.append(
                {
                    "id": f"fixed-{idx}",
                    "type": "Fixed",
                    "code": code,
                    "message": message,  # Generic message as the main text
                    "fix": "",  # No additional fix text needed
                    "fixed": True,
                    "items": items,  # List of specific changes
                    "count": len(items),
                }
            )
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
