import shutil
from pathlib import Path

from cognite.neat.constants import EXAMPLE_GRAPHS, EXAMPLE_RULES, EXAMPLE_WORKFLOWS


def copy_examples_to_directory(target_data_dir: Path):
    """
    Copier over all the examples to the target_data_directory,
    without overwriting

    Args:
        target_data_dir : The target directory

    """

    print(f"Copying examples into {target_data_dir}")
    _copy_examples(EXAMPLE_RULES, target_data_dir / "rules")
    _copy_examples(EXAMPLE_GRAPHS, target_data_dir / "source-graphs")
    _copy_examples(EXAMPLE_WORKFLOWS, target_data_dir / "workflows")
    (target_data_dir / "staging").mkdir(exist_ok=True, parents=True)


def create_data_dir_structure(target_data_dir: Path):
    """
    Create the data directory structure in empty directory

    Args:
        target_data_dir : The target directory

    """

    (target_data_dir / "rules").mkdir(exist_ok=True, parents=True)
    (target_data_dir / "source-graphs").mkdir(exist_ok=True, parents=True)
    (target_data_dir / "staging").mkdir(exist_ok=True, parents=True)
    (target_data_dir / "workflows").mkdir(exist_ok=True, parents=True)


def _copy_examples(source_dir: Path, target_dir: Path):
    for current in source_dir.rglob("*"):
        if current.is_dir():
            continue
        relative = current.relative_to(source_dir)
        if not (target := target_dir / relative).exists():
            target.parent.mkdir(exist_ok=True, parents=True)
            shutil.copy2(current, target)
