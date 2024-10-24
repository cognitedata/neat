from graphlib import CycleError
from typing import cast

from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import NeatValueError, PropertyDefinitionError
from cognite.neat._rules.models._base_rules import SheetList
from cognite.neat._rules.models.asset._rules import AssetProperty, AssetRules
from cognite.neat._rules.models.entities import AssetEntity, AssetFields, ClassEntity
from cognite.neat._rules.models.information._validation import InformationPostValidation


class AssetPostValidation(InformationPostValidation):
    def validate(self) -> IssueList:
        self.issue_list = super().validate()
        self._parent_property_point_to_class()
        self._circular_dependency()
        return self.issue_list

    def _parent_property_point_to_class(self) -> None:
        for property_ in cast(SheetList[AssetProperty], self.properties):
            for implementation in property_.implementation:
                if (
                    isinstance(implementation, AssetEntity)
                    and implementation.property_ == AssetFields.parentExternalId
                    and not isinstance(property_.value_type, ClassEntity)
                ):
                    self.issue_list.append(
                        PropertyDefinitionError(
                            property_.class_,
                            "class",
                            property_.property_,
                            "parentExternalId is only allowed to "
                            f"point to a Class not {type(property_.value_type).__name__}",
                        )
                    )

    def _circular_dependency(self) -> None:
        from cognite.neat._rules.analysis import AssetAnalysis

        try:
            _ = AssetAnalysis(cast(AssetRules, self.rules)).class_topological_sort()
        except CycleError as error:
            self.issue_list.append(
                NeatValueError(f"Invalid Asset Hierarchy, circular dependency detected: {error.args[1]}")
            )
