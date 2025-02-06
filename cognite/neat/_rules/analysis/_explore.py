from collections import defaultdict

from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._rules.models.information import InformationProperty


class Explore:
    def __init__(self, information: InformationRules, dms: DMSRules | None) -> None:
        self._information = information
        self._dms = dms

    def properties_by_classes(
        self,
        include_inherited: bool = False,
    ) -> dict[ClassEntity, list[InformationProperty]]:
        properties_by_classes = defaultdict(list)
        for prop in self._information.properties:
            properties_by_classes[prop.class_].append(prop)

        return properties_by_classes
