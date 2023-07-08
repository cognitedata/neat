import filecmp
from pathlib import Path

from cognite.neat.constants import EXAMPLES_DIRECTORY
from cognite.neat.core import rules
from cognite.neat.core.loader.config import copy_examples_to_directory
from tests import config


def test_load_excel():
    assert rules.loader.excel_file_to_table_by_name(config.TNT_TRANSFORMATION_RULES)


def test_copy_examples_to_directory(tmp_path: Path):
    target_path = tmp_path / "data"

    copy_examples_to_directory(target_path)

    rapport = filecmp.dircmp(target_path, EXAMPLES_DIRECTORY)
    assert not rapport.diff_files
