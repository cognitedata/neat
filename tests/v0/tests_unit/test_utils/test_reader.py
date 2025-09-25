import pytest

from cognite.neat.v0.core._utils.reader import (
    GitHubReader,
    HttpFileReader,
    NeatReader,
    PathReader,
)
from tests.v0.data import GraphData


class TestNeatReader:
    def test_create_path(self) -> None:
        reader = NeatReader.create(GraphData.car_py)
        assert isinstance(reader, PathReader)

    def test_create_str(self) -> None:
        reader = NeatReader.create(str(GraphData.car_py))
        assert isinstance(reader, PathReader)

    def test_create_github_url(self) -> None:
        reader = NeatReader.create(
            "https://github.com/cognitedata/toolkit-data/blob/main/data/publicdata/sharepoint.Table.csv"
        )
        assert isinstance(reader, GitHubReader)

    def test_create_any_url(self) -> None:
        reader = NeatReader.create("https://apps-cdn.cogniteapp.com/toolkit/publicdata/valhall_file_metadata.csv")
        assert isinstance(reader, HttpFileReader)


class TestGithubReader:
    @pytest.mark.parametrize(
        "url, repo, path",
        [
            (
                "https://github.com/cognitedata/toolkit-data/blob/main/data/publicdata/sharepoint.Table.csv",
                "cognitedata/toolkit-data",
                "data/publicdata/sharepoint.Table.csv",
            ),
            (
                "https://api.github.com/repos/cognitedata/toolkit-data/contents/data/publicdata/sharepoint.Table.csv",
                "cognitedata/toolkit-data",
                "data/publicdata/sharepoint.Table.csv",
            ),
        ],
    )
    def test_parse_url(self, url: str, repo: str, path: str) -> None:
        actual_repo, actual_path = GitHubReader._parse_url(url)
        assert actual_repo == repo
        assert actual_path == path

    def test_iterate_file(self) -> None:
        reader = GitHubReader(
            "https://github.com/cognitedata/toolkit-data/blob/main/data/publicdata/sharepoint.Table.csv"
        )
        size = reader.size()
        assert size > 0
        chunks = list(reader.iterate(10))
        read = reader.read_text()
        assert "".join(chunks) == read
