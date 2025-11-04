from collections.abc import Iterator, Sequence
from typing import TypeVar

T_Sequence = TypeVar("T_Sequence", bound=Sequence)


def chunker_sequence(sequence: T_Sequence, size: int) -> Iterator[T_Sequence]:
    """Yield successive n-sized chunks from sequence."""
    for i in range(0, len(sequence), size):
        # MyPy does not expect sequence[i : i + size] to be of type T_Sequence
        yield sequence[i : i + size]  # type: ignore[misc]
