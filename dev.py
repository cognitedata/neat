"""This is an internal CLI for the development team. It is intended for automating development tasks."""

from pathlib import Path
from typing import Literal, get_args

import marko
import marko.block
import marko.element
import marko.inline
import typer
from packaging.version import Version, parse

REPO_ROOT = Path(__file__).parent
VERSION_FILE = REPO_ROOT / "cognite" / "neat" / "_version.py"


VALID_CHANGELOG_HEADERS = {"Added", "Changed", "Removed", "Fixed", "Improved"}
BUMP_OPTIONS = Literal["major", "minor", "patch", "skip"]
VALID_BUMP_OPTIONS = get_args(BUMP_OPTIONS)
LAST_GIT_MESSAGE_FILE = REPO_ROOT / "last_git_message.txt"
CHANGELOG_ENTRY_FILE = REPO_ROOT / "last_changelog_entry.md"
LAST_VERSION = REPO_ROOT / "last_version.txt"
VERSION_PLACEHOLDER = "0.0.0"
VERSION_FILES = (
    REPO_ROOT / "pyproject.toml",
    REPO_ROOT / "cognite" / "neat" / "_version.py",
)

dev_app = typer.Typer(
    add_completion=False,
    help=__doc__,
    pretty_exceptions_short=False,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)


@dev_app.command()
def bump(verbose: bool = False) -> None:
    last_version_str = LAST_VERSION.read_text().strip().removeprefix("v")
    try:
        last_version = parse(last_version_str)
    except ValueError:
        print(f"Invalid last version: {last_version_str}")
        raise SystemExit(1) from None

    bump_text, _ = _read_last_commit_message()
    version_bump = _get_change(bump_text)

    if version_bump == "skip":
        print("No changes to release.")
        return
    if version_bump == "major":
        new_version = Version(f"{last_version.major + 1}.0.0")
    elif version_bump == "minor":
        new_version = Version(f"{last_version.major}.{last_version.minor + 1}.0")
    elif version_bump == "patch":
        new_version = Version(f"{last_version.major}.{last_version.minor}.{last_version.micro + 1}")
    else:
        raise typer.BadParameter("You must specify one of major, minor, patch, alpha, or beta.")

    for file in VERSION_FILES:
        file.write_text(file.read_text().replace(str(VERSION_PLACEHOLDER), str(new_version), 1))
        if verbose:
            typer.echo(f"Bumped version from {last_version} to {new_version} in {file}.")

    typer.echo(f"Bumped version from {last_version} to {new_version} in {len(VERSION_FILES)} files.")


@dev_app.command("changelog")
def create_changelog_entry() -> None:
    bump_text, changelog_text = _read_last_commit_message()
    version_bump = _get_change(bump_text)
    if version_bump == "skip":
        print("No changes to release.")
        return
    if changelog_text is None:
        print(f"No changelog entry found in the last commit message. This is required for a {version_bump} release.")
        raise SystemExit(1)
    _validate_changelog_entry(changelog_text)

    CHANGELOG_ENTRY_FILE.write_text(changelog_text, encoding="utf-8")
    print(f"Changelog entry written to {CHANGELOG_ENTRY_FILE}.")


def _read_last_commit_message() -> tuple[str, str | None]:
    last_git_message = LAST_GIT_MESSAGE_FILE.read_text()
    if "## Bump" not in last_git_message:
        print("No bump entry found in the last commit message.")
        raise SystemExit(1)

    after_bump = last_git_message.split("## Bump")[1].strip()
    if "## Changelog" not in after_bump:
        return after_bump, None

    bump_text, changelog_text = after_bump.split("## Changelog")

    if "-----" in changelog_text:
        # Co-authors section
        changelog_text = changelog_text.split("-----")[0].strip()

    return bump_text, changelog_text


def _validate_changelog_entry(changelog_text: str) -> None:
    items = [item for item in marko.parse(changelog_text).children if not isinstance(item, marko.block.BlankLine)]
    if not items:
        print("No entries found in the changelog section of the changelog.")
        raise SystemExit(1)
    seen_headers = set()

    last_header: str = ""
    for item in items:
        if isinstance(item, marko.block.Heading):
            if last_header:
                print(f"Expected a list of changes after the {last_header} header.")
                raise SystemExit(1)
            elif item.level != 3:
                print(f"Unexpected header level in changelog: {item}. Should be level 3.")
                raise SystemExit(1)
            elif not isinstance(item.children[0], marko.inline.RawText):
                print(f"Unexpected header in changelog: {item}.")
                raise SystemExit(1)
            header_text = item.children[0].children
            if header_text not in VALID_CHANGELOG_HEADERS:
                print(f"Unexpected header in changelog: {header_text}. Must be one of {VALID_CHANGELOG_HEADERS}.")
                raise SystemExit(1)
            if header_text in seen_headers:
                print(f"Duplicate header in changelog: {header_text}.")
                raise SystemExit(1)
            seen_headers.add(header_text)
            last_header = header_text
        elif isinstance(item, marko.block.List):
            if not last_header:
                print("Expected a header before the list of changes.")
                raise SystemExit(1)
            last_header = ""
        else:
            print(f"Unexpected item in changelog: {item}.")
            raise SystemExit(1)


def _get_change(bump_text: str) -> Literal["major", "minor", "patch", "skip"]:
    items = [item for item in marko.parse(bump_text).children if not isinstance(item, marko.block.BlankLine)]
    if not items:
        print("No items found in the bump section of the commit message.")
        raise SystemExit(1)
    item = items[0]
    if not isinstance(item, marko.block.List):
        print("The first item in the bump must be a list with the type of change.")
        raise SystemExit(1)
    selected: list[Literal["major", "minor", "patch", "skip"]] = []
    for child in item.children:
        if not isinstance(child, marko.block.ListItem):
            print(f"Unexpected item in bump section: {child}")
            raise SystemExit(1)
        if not isinstance(child.children[0], marko.block.Paragraph):
            print(f"Unexpected item in bump section: {child.children[0]}")
            raise SystemExit(1)
        if not isinstance(child.children[0].children[0], marko.inline.RawText):
            print(f"Unexpected item in bump section: {child.children[0].children[0]}")
            raise SystemExit(1)
        list_text = child.children[0].children[0].children
        if list_text.startswith("[ ]"):
            continue
        elif list_text.casefold().startswith("[x]"):
            change_type = list_text[3:].strip()
            if change_type.casefold() not in VALID_BUMP_OPTIONS:
                print(f"Unexpected change type in bump section {change_type}")
                raise SystemExit(1)
            selected.append(change_type.casefold())
        else:
            print(f"Unexpected item in bump section: {list_text}")
            raise SystemExit(1)

    if len(selected) > 1:
        print(f"You can only select one type of change, got {selected}.")
        raise SystemExit(1)
    if not selected:
        print("You must select exactly one type of change, got nothing.")
        raise SystemExit(1)
    return selected[0]


if __name__ == "__main__":
    dev_app()
