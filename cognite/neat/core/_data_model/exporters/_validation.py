from collections import defaultdict
from collections.abc import Iterable

from cognite.neat.core._data_model.models.conceptual import ConceptualProperty
from cognite.neat.core._data_model.models.entities import ConceptEntity


def duplicated_properties(
    properties: Iterable[ConceptualProperty],
) -> dict[tuple[ConceptEntity, str], list[tuple[int, ConceptualProperty]]]:
    class_properties_by_id: dict[
        tuple[ConceptEntity, str], list[tuple[int, ConceptualProperty]]
    ] = defaultdict(list)
    for prop_no, prop in enumerate(properties):
        class_properties_by_id[(prop.concept, prop.property_)].append((prop_no, prop))
    return {k: v for k, v in class_properties_by_id.items() if len(v) > 1}
