from collections import Counter
from collections.abc import Iterable, Sequence
from typing import TypeVar

T_Element = TypeVar("T_Element")


def remove_none_elements_from_set(s: set[T_Element]) -> set[T_Element]:
    return {x for x in s if x is not None}


def most_occurring_element(list_of_elements: list[T_Element]) -> T_Element:
    counts = Counter(list_of_elements)
    return counts.most_common(1)[0][0]


def chunker(sequence: Sequence[T_Element], chunk_size: int) -> Iterable[Sequence[T_Element]]:
    for i in range(0, len(sequence), chunk_size):
        yield sequence[i : i + chunk_size]


def remove_list_elements(input_list: list, elements_to_remove: list) -> list:
    return [element for element in input_list if element not in elements_to_remove]
