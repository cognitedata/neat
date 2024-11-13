import pytest

from cognite.neat._utils.neat_io import GitHubFile, NeatPath, NeatReader
from tests.data import DATA_DIR


class TestNeatReader:
    def test_create(self) -> None:
        reader = NeatReader.create(DATA_DIR / "car.py")
        assert isinstance(reader, NeatPath)

    def test_str(self) -> None:
        reader = NeatReader.create(str(DATA_DIR / "car.py"))
        assert isinstance(reader, NeatPath)

    def test_github(self) -> None:
        reader = NeatReader.create(
            "https://github.com/cognitedata/toolkit-data/blob/main/data/publicdata/sharepoint.Table.csv"
        )
        assert isinstance(reader, GitHubFile)


class TestGithubFile:
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
        actual_repo, actual_path = GitHubFile._parse_url(url)
        assert actual_repo == repo
        assert actual_path == path
