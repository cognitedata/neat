from abc import ABC, abstractmethod

from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models._rules import DMSRules, InformationRules


class BaseRulesValidator(ABC):
    """
    BaseRulesImporter class which all validators inherit from.
    """

    def __init__(self, rules: InformationRules | DMSRules, issue_list: IssueList):
        self.issue_list = issue_list
        self.rules = rules

    @abstractmethod
    def validate(self) -> IssueList:
        """
        Validates the rules.
        """
        raise NotImplementedError()
