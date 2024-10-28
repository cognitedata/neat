"""This is an internal CLI for the development team. It is intended for automating development tasks."""

from datetime import date
from pathlib import Path

import typer
from packaging.version import Version, parse

REPO_ROOT = Path(__file__).parent
CHANGELOG = REPO_ROOT / "docs" / "CHANGELOG.md"
VERSION_FILE = REPO_ROOT / "cognite" / "neat" / "_version.py"
TBD_HEADING = "## TBD"

dev_app = typer.Typer(
    add_completion=False,
    help=__doc__,
    pretty_exceptions_short=False,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_enable=False,
)


@dev_app.command()
def bump(
    major: bool = False,
    minor: bool = False,
    patch: bool = False,
    alpha: bool = False,
    beta: bool = False,
    verbose: bool = False,
) -> None:
    version_files = [
        REPO_ROOT / "pyproject.toml",
        REPO_ROOT / "cognite" / "neat" / "_version.py",
        REPO_ROOT / "Makefile",
    ]
    version_file_content = VERSION_FILE.read_text().split("\n")[0]
    version_raw = version_file_content.split(" = ")[1].strip().strip('"')

    version = parse(version_raw)

    if alpha and version.is_prerelease and version.pre[0] == "a":
        suffix = f"a{version.pre[1] + 1}"
    elif alpha and version.is_prerelease and version.pre[0] == "b":
        raise typer.BadParameter("Cannot bump to alpha version when current version is a beta prerelease.")
    elif alpha and not version.is_prerelease:
        suffix = "a1"
    elif beta and version.is_prerelease and version.pre[0] == "a":
        suffix = "b1"
    elif beta and version.is_prerelease and version.pre[0] == "b":
        suffix = f"b{version.pre[1] + 1}"
    elif beta and not version.is_prerelease:
        raise typer.BadParameter("Cannot bump to beta version when current version is not an alpha prerelease.")
    else:
        suffix = ""

    if major:
        new_version = Version(f"{version.major + 1}.0.0{suffix}")
    elif minor:
        new_version = Version(f"{version.major}.{version.minor + 1}.0{suffix}")
    elif patch:
        new_version = Version(f"{version.major}.{version.minor}.{version.micro + 1}{suffix}")
    elif alpha or beta:
        new_version = Version(f"{version.major}.{version.minor}.{version.micro}{suffix}")
    else:
        raise typer.BadParameter("You must specify one of major, minor, patch, alpha, or beta.")

    # Update the changelog
    changelog = CHANGELOG.read_text()
    if TBD_HEADING not in changelog:
        raise ValueError(
            f"There are no changes to release. The changelog does not contain a TBD section: {TBD_HEADING}."
        )

    today = date.today().strftime("%d-%m-%Y")
    new_heading = f"## [{new_version}] - {today}"

    changelog = changelog.replace(TBD_HEADING, new_heading)
    CHANGELOG.write_text(changelog)
    typer.echo(f"Updated changelog with new heading: {new_heading}")

    for file in version_files:
        file.write_text(file.read_text().replace(str(version), str(new_version), 1))
        if verbose:
            typer.echo(f"Bumped version from {version} to {new_version} in {file}.")

    typer.echo(f"Bumped version from {version} to {new_version} in {len(version_files)} files.")


if __name__ == "__main__":
    dev_app()
