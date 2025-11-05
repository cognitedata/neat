from collections import UserList

from cognite.neat._utils.collection import chunker_sequence


class MyList(UserList): ...


class TestChunkerSequence:
    def test_chunker_sequence(self) -> None:
        data = MyList([1, 2, 3, 4, 5, 6, 7, 8, 9])
        chunks = list(chunker_sequence(data, size=4))

        for chunk in chunks:
            assert isinstance(chunk, MyList)
        # MyList([1, 2, 3, 4]) == [1, 2, 3, 4] evaluates to True
        assert chunks == [
            [1, 2, 3, 4],
            [5, 6, 7, 8],
            [9],
        ]

    def test_chunker_sequence_empty(self) -> None:
        assert list(chunker_sequence([], size=3)) == []
