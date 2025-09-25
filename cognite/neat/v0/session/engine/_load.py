import os
import re
import shutil
import sys
import tempfile
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Literal, cast

from cognite.client import CogniteClient
from packaging.version import Version
from packaging.version import parse as parse_version

from cognite.neat._version import __engine__
from cognite.neat.v0.core._issues.errors import NeatValueError

ENVIRONMENT_VARIABLE = "NEATENGINE"
PACKAGE_NAME = "neatengine"
PYVERSION = f"{sys.version_info.major}{sys.version_info.minor}"


def load_neat_engine(client: CogniteClient | None, location: Literal["newest", "cache"]) -> str | None:
    if location not in ["newest", "cache"]:
        raise NeatValueError(f"Cannot load engine from location: {location}")

    if not __engine__.startswith("^"):
        # Using value error as this is a developer error
        raise ValueError(f"Invalid engine version: {__engine__}")

    lower_bound = parse_version(__engine__[1:])
    upper_bound = Version(f"{lower_bound.major + 1}.0.0")

    cache_dir = Path(tempfile.gettempdir()) / PACKAGE_NAME
    cache_dir.mkdir(exist_ok=True)
    pattern = re.compile(rf"{PACKAGE_NAME}-(\d+\.\d+\.\d+)-{PYVERSION}.zip")

    candidates: dict[Version, Callable[[], Path]] = {}
    if location == "cache" and cache_dir.exists():
        candidates = _load_from_path(cache_dir, pattern, lower_bound, upper_bound)

    if location == "newest" or not candidates:
        # Loading in reverse order of priority
        # 4. Downloads folder
        candidates = _load_from_path(Path.home() / "Downloads", pattern, lower_bound, upper_bound)
        # 3. Current working directory
        candidates.update(_load_from_path(Path.cwd(), pattern, lower_bound, upper_bound))
        # 2. CDF
        if client:
            candidates.update(_load_from_cdf(client, pattern, lower_bound, upper_bound, cache_dir))
        # 1. Environment variable
        if ENVIRONMENT_VARIABLE in os.environ:
            environ_path = Path(os.environ[ENVIRONMENT_VARIABLE])
            if environ_path.exists():
                candidates.update(_load_from_path(environ_path, pattern, lower_bound, upper_bound))
            else:
                warnings.warn(
                    f"Environment variable {ENVIRONMENT_VARIABLE} points to non-existing path: {environ_path}",
                    UserWarning,
                    stacklevel=2,
                )

    if not candidates:
        return None

    selected_version = max(candidates.keys(), default=None)
    if not selected_version:
        return None
    source_path = candidates[selected_version]()
    destination_path = cache_dir / source_path.name
    if not destination_path.exists():
        shutil.copy(source_path, destination_path)
    sys.path.append(str(destination_path))
    try:
        from neatengine._version import __version__ as engine_version  # type: ignore[import-not-found]
    except ImportError:
        return None
    return engine_version


def _load_from_path(
    path: Path, pattern: re.Pattern[str], lower_bound: Version, upper_bound: Version
) -> dict[Version, Callable[[], Path]]:
    if path.is_file() and (match := pattern.match(path.name)):
        version = parse_version(match.group(1))
        if lower_bound <= version < upper_bound:
            return {parse_version(match.group(1)): lambda: path}
        return {}
    elif path.is_dir():
        output: dict[Version, Callable[[], Path]] = {}
        for candidate in path.iterdir():
            if candidate.is_file() and (match := pattern.match(candidate.name)):
                version = parse_version(match.group(1))
                if lower_bound <= version < upper_bound:
                    # Setting default value to ensure we use the candidate from the current iteration
                    # If not set, the function will use the last candidate from the loop
                    def return_path(the_path: Path = candidate) -> Path:
                        return the_path

                    output[parse_version(match.group(1))] = return_path

        return output
    return {}


def _load_from_cdf(
    client: CogniteClient, pattern: re.Pattern[str], lower_bound: Version, upper_bound: Version, cache_dir: Path
) -> dict[Version, Callable[[], Path]]:
    file_metadata = client.files.list(
        limit=-1,
        data_set_external_ids=PACKAGE_NAME,
        external_id_prefix=PACKAGE_NAME,
        metadata={"python_version": PYVERSION},
    )
    output: dict[Version, Callable[[], Path]] = {}
    for file in file_metadata:
        name = cast(str, file.name)

        # Use function to lazily download file
        # Setting default value to ensure we use the file_id from the current iteration
        # If not set, the function will use the last file_id from the loop
        def download_file(file_id: int = file.id, filename: str = name) -> Path:
            client.files.download(cache_dir, file_id)
            return cache_dir / filename

        if match := pattern.match(name):
            version = parse_version(match.group(1))
            if lower_bound <= version < upper_bound:
                output[version] = download_file

    return output
