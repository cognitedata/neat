import shutil
from pathlib import Path

from cognite.neat.constants import EXAMPLE_GRAPHS, EXAMPLE_RULES, EXAMPLE_WORKFLOWS


def copy_examples_to_directory(target_data_dir: Path, suffix: str = ""):
    """
    Copier over all the examples to the target_data_directory,
    without overwriting

    Args:
        target_data_dir : The target directory
        suffix : The suffix to add to the directory names

    """

    print(f"Copying examples into {target_data_dir}")
    _copy_examples(EXAMPLE_RULES, target_data_dir / f"rules{suffix}")
    _copy_examples(EXAMPLE_GRAPHS, target_data_dir / f"source-graphs{suffix}")
    _copy_examples(EXAMPLE_WORKFLOWS, target_data_dir / f"workflows{suffix}")
    (target_data_dir / f"staging{suffix}").mkdir(exist_ok=True, parents=True)


def create_data_dir_structure(target_data_dir: Path, suffix: str = "") -> None:
    """
    Create the data directory structure in empty directory

    Args:
        target_data_dir : The target directory
        suffix : The suffix to add to the directory names

    """

    (target_data_dir / f"rules{suffix}").mkdir(exist_ok=True, parents=True)
    (target_data_dir / f"source-graphs{suffix}").mkdir(exist_ok=True, parents=True)
    (target_data_dir / f"staging{suffix}").mkdir(exist_ok=True, parents=True)
    (target_data_dir / f"workflows{suffix}").mkdir(exist_ok=True, parents=True)


def _copy_examples(source_dir: Path, target_dir: Path):
    for current in source_dir.rglob("*"):
        if current.is_dir():
            continue
        relative = current.relative_to(source_dir)
        if not (target := target_dir / relative).exists():
            target.parent.mkdir(exist_ok=True, parents=True)
            shutil.copy2(current, target)
