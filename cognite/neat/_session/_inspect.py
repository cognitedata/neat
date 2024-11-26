import difflib
from collections.abc import Callable
from typing import Literal, overload

import pandas as pd

from cognite.neat._constants import IN_NOTEBOOK
from cognite.neat._issues import IssueList
from cognite.neat._utils.upload import UploadResult, UploadResultCore, UploadResultList

from ._state import SessionState
from .exceptions import session_class_wrapper

try:
    from rich.markdown import Markdown as RichMarkdown

    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


@session_class_wrapper
class InspectAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.issues = InspectIssues(state)
        self.outcome = InspectOutcome(state)

    @property
    def properties(self) -> pd.DataFrame:
        """Returns the properties of the current data model."""
        return self._state.data_model.last_verified_rule[1].properties.to_pandas()


@session_class_wrapper
class InspectIssues:
    """Inspect issues of the current data model."""

    def __init__(self, state: SessionState) -> None:
        self._state = state

    @overload
    def __call__(
        self,
        search: str | None = None,
        return_dataframe: Literal[True] = (False if IN_NOTEBOOK else True),  # type: ignore[assignment]
    ) -> pd.DataFrame: ...

    @overload
    def __call__(
        self,
        search: str | None = None,
        return_dataframe: Literal[False] = (False if IN_NOTEBOOK else True),  # type: ignore[assignment]
    ) -> None: ...

    def __call__(
        self,
        search: str | None = None,
        return_dataframe: bool = (False if IN_NOTEBOOK else True),  # type: ignore[assignment]
    ) -> pd.DataFrame | None:
        """Returns the issues of the current data model."""
        issues = self._state.data_model.last_issues
        if not issues:
            self._print("No issues found.")

        if issues and search is not None:
            unique_types = {type(issue).__name__ for issue in issues}
            closest_match = set(difflib.get_close_matches(search, unique_types))
            issues = IssueList([issue for issue in issues if type(issue).__name__ in closest_match])

        issue_str = "\n".join(
            [f"  * **{type(issue).__name__}**: {issue.as_message(include_type=False)}" for issue in issues]
        )
        markdown_str = f"### {len(issues)} issues found\n\n{issue_str}"

        if IN_NOTEBOOK:
            from IPython.display import Markdown, display

            display(Markdown(markdown_str))
        elif RICH_AVAILABLE:
            from rich import print

            print(RichMarkdown(markdown_str))

        if return_dataframe:
            return issues.to_pandas()
        return None

    def _print(self, message: str) -> None:
        if IN_NOTEBOOK:
            from IPython.display import Markdown, display

            display(Markdown(message))
        else:
            print(message)

    def __repr__(self) -> str:
        return self.__repr_html__()

    def __repr_html__(self) -> str:
        return (
            "Inspect issues by calling .inspect.issues() or "
            "search for specific issues by calling .inspect.issues('MyTypeWarning')."
        )


@session_class_wrapper
class InspectOutcome:
    def __init__(self, state: SessionState) -> None:
        self.data_model = InspectUploadOutcome(lambda: state.data_model.last_outcome)
        self.instances = InspectUploadOutcome(lambda: state.instances.last_outcome)


@session_class_wrapper
class InspectUploadOutcome:
    def __init__(self, get_last_outcome: Callable[[], UploadResultList]) -> None:
        self._get_last_outcome = get_last_outcome

    @staticmethod
    def _as_set(value: str | list[str] | None) -> set[str] | None:
        if value is None:
            return None
        if isinstance(value, str):
            return {value}
        return set(value)

    @overload
    def __call__(
        self,
        name: str | list[str] | None = None,
        has_errors: bool = False,
        has_issues: bool = False,
        return_dataframe: Literal[False] = (False if IN_NOTEBOOK else True),  # type: ignore[assignment]
    ) -> None: ...

    @overload
    def __call__(
        self,
        name: str | list[str] | None = None,
        has_errors: bool = False,
        has_issues: bool = False,
        return_dataframe: Literal[True] = (False if IN_NOTEBOOK else True),  # type: ignore[assignment]
    ) -> pd.DataFrame: ...

    def __call__(
        self,
        name: str | list[str] | None = None,
        has_errors: bool = False,
        has_issues: bool = False,
        return_dataframe: bool = (False if IN_NOTEBOOK else True),  # type: ignore[assignment]
    ) -> pd.DataFrame | None:
        """Returns the outcome of the last upload."""
        outcome = self._get_last_outcome()
        name_set = self._as_set(name)

        def outcome_filter(item: UploadResultCore) -> bool:
            nonlocal name_set
            if name_set and item.name not in name_set:
                return False
            if has_errors and not item.error_messages:
                return False
            if has_issues and not item.issues:
                return False
            return True

        outcome = UploadResultList([item for item in outcome if outcome_filter(item)])
        if IN_NOTEBOOK:
            from IPython.display import Markdown, display

            lines: list[str] = []
            for item in outcome:
                lines.append(f"### {item.name}")
                if unique_errors := set(item.error_messages):
                    lines.append("#### Errors")
                    for error in unique_errors:
                        lines.append(f"  * {error}")
                if unique_issue_messages := set([issue.as_message() for issue in item.issues]):
                    lines.append("#### Issues")
                    for issue in unique_issue_messages:
                        lines.append(f"  * {issue}")
                if isinstance(item, UploadResult):
                    dumped = item.dump(aggregate=False)
                    for key, value in dumped.items():
                        if key in ["name", "error_messages", "issues"]:
                            continue
                        lines.append(f"#### {key}")
                        if isinstance(value, list):
                            total = len(value)
                            for i, v in enumerate(value):
                                if key in ["created", "updated", "changed"]:
                                    if i < 50:
                                        lines.append(f"  * {v}")
                                    elif i == 50 and total > 50:
                                        lines.append(f"  * ... {total-50} more")
                                    elif i == 50 and total == 50:
                                        lines.append(f"  * {v}")
                                else:
                                    lines.append(f"  * {v}")

                        else:
                            lines.append(f"  * {value}")

            display(Markdown("\n".join(lines)))

        if return_dataframe:
            return outcome.to_pandas()
        return None
