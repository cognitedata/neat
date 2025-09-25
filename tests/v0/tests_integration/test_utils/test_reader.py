import pytest
from requests.exceptions import HTTPError

from cognite.neat.v0.core._utils.reader import NeatReader


@pytest.fixture(scope="session")
def http_file_reader() -> NeatReader:
    reader = NeatReader.create("https://apps-cdn.cogniteapp.com/toolkit/publicdata/valhall_file_metadata.csv")
    assert reader.exists()
    return reader


@pytest.fixture(scope="session")
def github_reader() -> NeatReader:
    reader = NeatReader.create(
        "https://github.com/cognitedata/toolkit-data/blob/main/data/publicdata/valhall_file_metadata.csv"
    )
    try:
        assert reader.exists()
    except HTTPError as e:
        if 400 <= e.response.status_code < 500:
            pytest.skip(f"Rate limit exceeded for GitHub API: {e}")
    return reader


class TestHttpFileReader:
    def test_read_text(self, http_file_reader: NeatReader) -> None:
        text = http_file_reader.read_text()
        assert text.startswith("name,source,mime_type")

    def test_size(self, http_file_reader: NeatReader) -> None:
        assert http_file_reader.size() > 0

    def test_iterate(self, http_file_reader: NeatReader) -> None:
        chunk = next(iter(http_file_reader.iterate(256)))
        assert len(chunk) > 0
        assert chunk.startswith("name,source,mime_type")


class TestGithubReader:
    def test_read_text(self, github_reader: NeatReader) -> None:
        text = github_reader.read_text()
        assert text.startswith("name,source,mime_type")

    def test_size(self, github_reader: NeatReader) -> None:
        assert github_reader.size() > 0

    def test_iterate(self, github_reader: NeatReader) -> None:
        chunk = next(iter(github_reader.iterate(256)))
        assert len(chunk) > 0
        assert chunk.startswith("name,source,mime_type")
