import subprocess
from pathlib import Path


def get_repo_root() -> Path | None:
    """Get the root path of the git repository.

    Raises:
        RuntimeError: If git is not installed or the current directory is not in a git repository

    """
    try:
        result = subprocess.run("git rev-parse --show-toplevel".split(), stdout=subprocess.PIPE)
    except FileNotFoundError:
        # Git is not installed or not found in PATH
        return None
    output = result.stdout.decode().strip()
    if not output:
        # Not in a git repository
        return None
    return Path(output)
