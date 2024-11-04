import difflib
from typing import Literal, overload

import pandas as pd

from cognite.neat._constants import IN_NOTEBOOK
from cognite.neat._issues import IssueList

from ._state import SessionState
from .exceptions import intercept_session_exceptions


@intercept_session_exceptions
class InspectAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.issues = InspectIssues(state)

    @property
    def properties(self) -> pd.DataFrame:
        """Returns the properties of the current data model."""
        return self._state.last_verified_rule.properties.to_pandas()


@intercept_session_exceptions
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
        issues = self._state.last_issues
        if not issues:
            self._print("No issues found.")

        if issues and search is not None:
            unique_types = {type(issue).__name__ for issue in issues}
            closest_match = set(difflib.get_close_matches(search, unique_types))
            issues = IssueList([issue for issue in issues if type(issue).__name__ in closest_match])

        if IN_NOTEBOOK:
            from IPython.display import Markdown, display

            issue_str = "\n".join(
                [f"  * **{type(issue).__name__}**: {issue.as_message(include_type=False)}" for issue in issues]
            )
            message = f"### {len(issues)} issues found\n\n{issue_str}"
            display(Markdown(message))

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
