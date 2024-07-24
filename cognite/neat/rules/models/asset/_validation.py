from graphlib import CycleError
from typing import cast

from cognite.neat.issues import IssueList
from cognite.neat.rules import issues
from cognite.neat.rules.models._base import SheetList
from cognite.neat.rules.models.asset._rules import AssetProperty, AssetRules
from cognite.neat.rules.models.entities import AssetEntity, AssetFields, ClassEntity
from cognite.neat.rules.models.information._validation import InformationPostValidation


class AssetPostValidation(InformationPostValidation):
    def validate(self) -> IssueList:
        self.issue_list = super().validate()
        self._parent_property_point_to_class()
        self._circular_dependency()
        return self.issue_list

    def _parent_property_point_to_class(self) -> None:
        class_property_with_data_value_type = []
        for property_ in cast(SheetList[AssetProperty], self.properties):
            for implementation in property_.implementation:
                if (
                    isinstance(implementation, AssetEntity)
                    and implementation.property_ == AssetFields.parentExternalId
                    and not isinstance(property_.value_type, ClassEntity)
                ):
                    class_property_with_data_value_type.append((property_.class_.suffix, property_.property_))

        if class_property_with_data_value_type:
            self.issue_list.append(
                issues.spreadsheet.AssetParentPropertyPointsToDataValueTypeError(class_property_with_data_value_type)
            )

    def _circular_dependency(self) -> None:
        from cognite.neat.rules.analysis import AssetAnalysis

        try:
            _ = AssetAnalysis(cast(AssetRules, self.rules)).class_topological_sort()
        except CycleError as error:
            self.issue_list.append(issues.spreadsheet.AssetRulesHaveCircularDependencyError(error.args[1]))
