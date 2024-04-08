from copy import deepcopy
from typing import cast

from cognite.neat.rules._analysis import DataModelingScenario, InformationArchitectRulesAnalysis
from cognite.neat.rules.issues import IssueList, handle_issues
from cognite.neat.rules.models._rules import InformationRules
from cognite.neat.rules.models._rules.base import SchemaCompleteness

from ._base import BaseRulesValidator


class DataModelingScenarioValidator(BaseRulesValidator):
    def validate(self) -> IssueList:
        if isinstance(self.rules, InformationRules):
            return self._validate_information_rules()
        else:
            return self.issue_list

    def _validate_information_rules(self) -> IssueList:
        analysis = InformationArchitectRulesAnalysis(cast(InformationRules, self.rules))
        if analysis.data_modeling_scenario == DataModelingScenario.build_solution:
            print("Here")
            cp_rules = deepcopy(cast(InformationRules, self.rules))
            cp_rules.reference = None

            cp_rules.classes.data.extend(analysis.referred_classes)
            cp_rules.properties.data.extend(analysis.referred_classes_properties)
            cp_rules.metadata.schema_ = SchemaCompleteness.complete

            with handle_issues(self.issue_list):
                _ = InformationRules(**cp_rules.model_dump())

        return self.issue_list
