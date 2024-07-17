from typing import cast

from cognite.neat.rules import issues
from cognite.neat.rules.issues.base import IssueList
from cognite.neat.rules.models._base import SheetList
from cognite.neat.rules.models.asset._rules import AssetProperty
from cognite.neat.rules.models.entities import AssetEntity, AssetFields, ClassEntity
from cognite.neat.rules.models.information._validation import InformationPostValidation


class AssetPostValidation(InformationPostValidation):
    def validate(self) -> IssueList:
        self.issue_list = super().validate()
        self._parent_property_point_to_class()
        return self.issue_list

    def _parent_property_point_to_class(self) -> None:
        compromised_class_property = []
        for property_ in cast(SheetList[AssetProperty], self.properties):
            for implementation in property_.implementation:
                if (
                    isinstance(implementation, AssetEntity)
                    and implementation.property_ == AssetFields.parent_external_id
                    and not isinstance(property_.value_type, ClassEntity)
                ):
                    compromised_class_property.append((property_.class_.suffix, property_.property_))

        if compromised_class_property:
            self.issue_list.append(
                issues.spreadsheet.AssetParentPropertyPointsToDataValueTypeError(compromised_class_property)
            )
