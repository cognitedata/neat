from collections import Counter
from collections.abc import Iterable, Sequence
from typing import TypeVar

from cognite.neat._config import GLOBAL_CONFIG
from cognite.neat._constants import IN_PYODIDE

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


def iterate_progress_bar(iterable: Iterable[T_Element], total: int, description: str) -> Iterable[T_Element]:
    if IN_PYODIDE or GLOBAL_CONFIG.progress_bar in ("infer", "tqdm"):
        try:
            from tqdm import tqdm
        except ModuleNotFoundError:
            return iterable
        return tqdm(iterable, total=total, desc=description)

    elif GLOBAL_CONFIG.progress_bar == "tqdm-notebook":
        try:
            from tqdm.notebook import tqdm as tqdm_notebook
        except ModuleNotFoundError:
            return iterable
        return tqdm_notebook(iterable, total=total, desc=description)
    elif GLOBAL_CONFIG.progress_bar in ("infer", "rich"):
        # Progress bar from rich requires multi-threading, which is not supported in Pyodide
        try:
            from rich.progress import track
        except ModuleNotFoundError:
            return iterable

        return track(
            iterable,
            total=total,
            description=description,
        )
    elif GLOBAL_CONFIG.progress_bar is None:
        return iterable
    else:
        raise ValueError(f"Unsupported progress bar type: {GLOBAL_CONFIG.progress_bar}")


def iterate_progress_bar_if_above_config_threshold(
    iterable: Iterable[T_Element], total: int, description: str
) -> Iterable[T_Element]:
    if GLOBAL_CONFIG.use_iterate_bar_threshold and total > GLOBAL_CONFIG.use_iterate_bar_threshold:
        return iterate_progress_bar(iterable, total, description)
    return iterable
