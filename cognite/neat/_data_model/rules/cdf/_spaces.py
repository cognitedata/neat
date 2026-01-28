from cognite.neat._data_model._constants import COGNITE_APP_SPACES, COGNITE_SPACES
from cognite.neat._data_model.rules.cdf._base import CDFRule
from cognite.neat._issues import Recommendation

BASE_CODE = "NEAT-CDF-SPACES"


class EmptySpaces(CDFRule):
    """Rule that checks for empty spaces in CDF.

    ## What it does
    This rule checks if there are any empty spaces in CDF.

    ## Why is this bad?
    CDF projects typically have limits of 100 spaces, and having empty spaces can waste these valuable resources.
    Also, empty spaces can lead to confusion and mismanagement of resources within the CDF environment.
    They may indicate incomplete configurations or unused resources that could be cleaned up.

    ## Example
    A space `iamempty` with no associated resources such as Views, Containers or Data Models.


    """

    code = f"{BASE_CODE}-001"
    issue_type = Recommendation
    alpha = True

    def validate(self) -> list[Recommendation]:
        issues: list[Recommendation] = []

        if not self.validation_resources.space_statistics:
            return issues

        empty_spaces = set(self.validation_resources.space_statistics.empty_spaces()) - set(
            COGNITE_APP_SPACES + COGNITE_SPACES
        )

        for space in empty_spaces:
            issues.append(
                Recommendation(
                    message=f"Space '{space}' is empty and has no associated resources.",
                    code=self.code,
                    fix="Consider removing the empty space to maintain a clean CDF environment.",
                )
            )

        return issues
