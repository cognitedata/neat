from collections import defaultdict
from collections.abc import Iterable

from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._rules.models.information import InformationProperty


def duplicated_properties(
    properties: Iterable[InformationProperty],
) -> dict[tuple[ClassEntity, str], list[tuple[int, InformationProperty]]]:
    class_properties_by_id: dict[tuple[ClassEntity, str], list[tuple[int, InformationProperty]]] = defaultdict(list)
    for prop_no, prop in enumerate(properties):
        class_properties_by_id[(prop.class_, prop.property_)].append((prop_no, prop))
    return {k: v for k, v in class_properties_by_id.items() if len(v) > 1}
