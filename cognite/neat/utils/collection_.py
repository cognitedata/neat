from collections import Counter
from collections.abc import Sequence
from typing import TypeVar

T_Element = TypeVar("T_Element")


def remove_none_elements_from_set(s: set[T_Element]) -> set[T_Element]:
    return {x for x in s if x is not None}


def most_occurring_element(list_of_elements: list[T_Element]) -> T_Element:
    counts = Counter(list_of_elements)
    return counts.most_common(1)[0][0]


def chunker(sequence: Sequence[T_Element], chunk_size: int) -> list[Sequence[T_Element]]:
    return [sequence[i : i + chunk_size] for i in range(0, len(sequence), chunk_size)]
