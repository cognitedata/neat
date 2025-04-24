from pathlib import Path
from unittest.mock import MagicMock

import pytest

import dev
from tests.config import ROOT


def test_no_spaces_in_sub_folders() -> None:
    name_by_location: dict[Path, str] = {}
    to_check = [ROOT / "cognite"]
    while to_check:
        current = to_check.pop()
        for path in current.iterdir():
            if path.is_dir():
                if path.name not in {"node_modules"}:
                    to_check.append(path)
                if " " in path.name:
                    name_by_location[path] = path.name
                    raise ValueError(f"Subfolder with spaces found: {path}")

    assert not name_by_location, f"Subfolders with spaces found: {name_by_location}"


def get_create_changelog_entry_cases():
    yield pytest.param(
        """NEAT-899 Remove  template. solution_model()  (#1096)

# Description

Removing `template.solution_model()` as it is not robust to be public
method

## Bump

- [X] Patch
- [ ] Minor
- [ ] Skip

## Changelog
###  Removed

- Removed `template.solution_model()` as it is not robust to be public
method
        """,
        """
###  Removed

- Removed `template.solution_model()` as it is not robust to be public
method""",
        id="valid_changelog_entry",
    )


class TestReleaseProcess:
    @pytest.mark.parametrize("last_git_message, expected_changelog", list(get_create_changelog_entry_cases()))
    def test_create_changelog_entry(self, last_git_message: str, expected_changelog: str, monkeypatch) -> None:
        actual_changelog_entry: str | None = None
        last_git_message_file = MagicMock(spec=Path)
        last_git_message_file.read_text.return_value = last_git_message

        def mock_write_text(content, encoding=None):
            nonlocal actual_changelog_entry
            actual_changelog_entry = content

        changelog_file = MagicMock(spec=Path)
        changelog_file.write_text = mock_write_text

        monkeypatch.setattr(dev, "LAST_GIT_MESSAGE_FILE", last_git_message_file)
        monkeypatch.setattr(dev, "CHANGELOG_ENTRY_FILE", changelog_file)
        dev.create_changelog_entry()

        assert actual_changelog_entry is not None, "Changelog entry was not created"
        assert actual_changelog_entry == expected_changelog
