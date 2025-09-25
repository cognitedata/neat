from pathlib import Path
from unittest.mock import MagicMock

import pytest

import dev
from tests.v0.config import ROOT


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


def get_release_process_test_cases():
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
        "0.119.8\n",
        """
###  Removed

- Removed `template.solution_model()` as it is not robust to be public
method""",
        "0.119.9",
        id="Patch bump",
    )

    yield pytest.param(
        """Enable dummy property per user defined concept (#1079)
# Description

Enable adding dummy property for every user-defined concept when
creating extension template.
By default dummy property is formed as `idOfConceptGUID` , and it set to
be string, none mandatory.
Dummy properties help in avoiding to set filters in DMS.

## Bump

- [ ] Patch
- [x] Minor
- [ ] Skip

## Changelog
### Added
- Support for dummy properties in `template.extension()`

---------

Co-authored-by: Member <member@users.noreply.github.com>
Co-authored-by: Member <member@cognite.com>""",
        "0.119.8\n",
        """### Added
- Support for dummy properties in `template.extension()`""",
        "0.120.0",
        id="Minor bump with co-authors",
    )


class TestReleaseProcess:
    @pytest.mark.parametrize(
        "last_git_message, last_version, expected_changelog, expected_version", list(get_release_process_test_cases())
    )
    def test_bump_and_create_changelog_entry(
        self, last_git_message: str, last_version: str, expected_changelog: str, expected_version: str, monkeypatch
    ) -> None:
        actual_changelog_entry: str | None = None
        actual_version: str | None = None
        last_git_message_file = MagicMock(spec=Path)
        last_git_message_file.read_text.return_value = last_git_message
        last_version_file = MagicMock(spec=Path)
        last_version_file.read_text.return_value = last_version

        def mock_write_changelog(content, encoding=None):
            nonlocal actual_changelog_entry
            actual_changelog_entry = content

        changelog_file = MagicMock(spec=Path)
        changelog_file.write_text = mock_write_changelog

        version_file = MagicMock(spec=Path)
        version_file.read_text.return_value = dev.VERSION_PLACEHOLDER

        def mock_write_version(content, **_):
            nonlocal actual_version
            actual_version = content

        version_file.write_text = mock_write_version

        monkeypatch.setattr(dev, "LAST_GIT_MESSAGE_FILE", last_git_message_file)
        monkeypatch.setattr(dev, "LAST_VERSION", last_version_file)
        monkeypatch.setattr(dev, "CHANGELOG_ENTRY_FILE", changelog_file)
        monkeypatch.setattr(dev, "VERSION_FILES", [version_file])

        dev.bump()
        dev.create_changelog_entry()

        assert actual_changelog_entry is not None, "Changelog entry was not created"
        assert actual_changelog_entry == expected_changelog

        assert actual_version is not None, "Version was not updated"
        assert actual_version == expected_version
