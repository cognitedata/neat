from cognite.neat._data_model.rules.cdf._base import CDFRule
from cognite.neat._issues import Recommendation

BASE_CODE = "NEAT-CDF-SPACES"


class EmptySpaces(CDFRule):
    """Rule that checks for empty spaces in CDF.

    ## What it does
    This rule checks if there are any empty spaces in CDF.

    ## Why is this bad?
    Empty spaces can lead to confusion and mismanagement of resources within the CDF environment.
    They may indicate incomplete configurations or unused resources that could be cleaned up.

    ## Example
    A space `iamempty` with no associated resources such as Views, Containers or Data Models.


    """

    code = f"{BASE_CODE}-001"
    issue_type = Recommendation
    alpha = True

    def validate(self) -> list[Recommendation]:
        issues: list[Recommendation] = []

        all_spaces = set([space.space for space in self.validation_resources.cdf.spaces])
        used_spaces = set()

        for view in self.validation_resources.cdf.views:
            used_spaces.add(view.space)
        for container in self.validation_resources.cdf.containers:
            used_spaces.add(container.space)
        for data_model in self.validation_resources.cdf.data_model:
            used_spaces.add(data_model.space)

        if unused_spaces := all_spaces - used_spaces:
            for space in unused_spaces:
                issues.append(
                    Recommendation(
                        message=f"Space '{space}' is empty and has no associated resources.",
                        code=self.code,
                        fix="Consider removing the empty space to maintain a clean CDF environment.",
                    )
                )

        return issues
