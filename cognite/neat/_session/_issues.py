import json
import uuid
from collections import defaultdict
from typing import Any

from cognite.neat._config import NeatConfig
from cognite.neat._data_model._fix_actions import FixAction
from cognite.neat._data_model.deployer.data_classes import AddedField, RemovedField
from cognite.neat._data_model.models.dms._references import ContainerReference
from cognite.neat._data_model.rules.dms._base import DataModelRule
from cognite.neat._issues import ConsistencyError, IssueList, ModelSyntaxError, Recommendation
from cognite.neat._session._html._render import render
from cognite.neat._store import NeatStore
from cognite.neat._utils.auxiliary import get_concrete_subclasses


class Issues:
    """Class to handle issues in the NeatSession."""

    def __init__(self, store: NeatStore, config: NeatConfig) -> None:
        self._store = store
        self._config = config
        # Cache fixable validator codes
        self._fixable_codes = self._get_fixable_validator_codes()

    @staticmethod
    def _get_fixable_validator_codes() -> set[str]:
        """Get codes of all fixable validators."""
        fixable_codes = set()
        for validator_class in get_concrete_subclasses(DataModelRule):
            if validator_class.fixable:
                fixable_codes.add(validator_class.code)
        return fixable_codes

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

        Each fix is displayed individually, like issues. Field change details
        are included for fancy UI rendering.
        """
        serialized = []
        for idx, fix_action in enumerate(self._applied_fixes):
            item: dict[str, Any] = {
                "id": f"fixed-{idx}",
                "type": "Fixed",
                "code": fix_action.code,
                "message": fix_action.message or "",
                "fix": "",
                "fixed": True,
            }

            # Add fields for fancy UI rendering based on the field changes
            self._add_fix_ui_fields(fix_action, item)

            serialized.append(item)
        return serialized

    def _add_fix_ui_fields(self, fix_action: FixAction, item: dict[str, Any]) -> None:
        """Add UI rendering fields based on the fix action's field changes."""
        if not fix_action.changes:
            return

        # Get container name from resource_id
        container_name = ""
        if isinstance(fix_action.resource_id, ContainerReference):
            container_name = fix_action.resource_id.external_id

        # Check the first change to determine the fix type
        change = fix_action.changes[0]
        field_path = change.field_path

        if field_path.startswith("constraints."):
            constraint_id = field_path.split(".", 1)[1]
            item["fix_type"] = "constraint"
            item["source_name"] = container_name
            item["constraint_id"] = constraint_id

            if isinstance(change, AddedField):
                item["action_type"] = "add"
                # Get dest from the constraint definition
                if hasattr(change.new_value, "require"):
                    item["dest_name"] = change.new_value.require.external_id
            elif isinstance(change, RemovedField):
                item["action_type"] = "remove"
                # Get dest from the constraint definition
                if hasattr(change.current_value, "require"):
                    item["dest_name"] = change.current_value.require.external_id

        elif field_path.startswith("indexes."):
            index_id = field_path.split(".", 1)[1]
            item["fix_type"] = "index"
            item["container_name"] = container_name
            item["index_id"] = index_id

            # Get property_id from the index definition
            if isinstance(change, AddedField) and hasattr(change.new_value, "properties"):
                properties = change.new_value.properties
                if properties:
                    item["property_id"] = properties[0]

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

        # Count fixable issues (those generated by validators with fixable = True)
        fixable_count = sum(1 for issue in self._issues if issue.code in self._fixable_codes)

        # Only show Fixed tab if the alpha flag is enabled
        fixed_count = len(self._applied_fixes)
        if self._config.alpha.fix_validation_issues:
            fixed_tab_html = f"""<div class="stat-item stat-fixed" data-filter="Fixed">
                <span class="stat-number">{fixed_count}</span> Fixes
            </div>"""
        else:
            fixed_tab_html = ""

        template_vars = {
            "JSON": json.dumps(all_serialized),
            "total": stats["total"],
            "syntax_errors": stats["by_type"].get("ModelSyntaxError", 0),
            "consistency_errors": stats["by_type"].get("ConsistencyError", 0),
            "recommendations": stats["by_type"].get("Recommendation", 0),
            "fixable_count": fixable_count,
            "fixed_tab": fixed_tab_html,
            "unique_id": unique_id,
        }

        return render("issues", template_vars)
