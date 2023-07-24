import shutil
from pathlib import Path

from cognite.neat.workflows.constants import EXAMPLES_DIRECTORY


def copy_examples_to_directory(target_data_dir: Path):
    """
    Copier over all the examples to the target_data_directory,
    without overwriting


    Parameters
    ----------
    target_data_dir : The target directory


    """
    print(f"Copying examples into {target_data_dir}")
    for current in EXAMPLES_DIRECTORY.rglob("*"):
        if current.is_dir():
            continue
        relative = current.relative_to(EXAMPLES_DIRECTORY)
        if not (target := target_data_dir / relative).exists():
            target.parent.mkdir(exist_ok=True, parents=True)
            shutil.copy2(current, target)
