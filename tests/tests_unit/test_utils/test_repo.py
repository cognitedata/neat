from pathlib import Path
from unittest.mock import patch

import pytest

from cognite.neat._utils.repo import repo_root


class TestRepoRoot:
    def test_repo_root(self) -> None:
        input_path = Path.cwd()
        with patch("subprocess.run", return_value=type("CompletedProcess", (), {"stdout": str(input_path).encode()})):
            path = repo_root()
        assert path == input_path

    def test_repo_root_git_not_found(self) -> None:
        with (
            patch("subprocess.run", side_effect=FileNotFoundError("git not found")),
            pytest.raises(RuntimeError, match="Git is not installed or not found in PATH"),
        ):
            _ = repo_root()

    def test_repo_root_not_in_git_repo(self) -> None:
        with (
            patch("subprocess.run", return_value=type("CompletedProcess", (), {"stdout": b""})),
            pytest.raises(RuntimeError),
        ):
            _ = repo_root()
