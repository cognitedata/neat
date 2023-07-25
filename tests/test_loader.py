import filecmp
from pathlib import Path

from cognite.neat.constants import EXAMPLES_DIRECTORY
from cognite.neat.graph.extractors.config import copy_examples_to_directory
from cognite.neat.core.rules.models import TransformationRules


def test_load_excel(transformation_rules: TransformationRules):
    assert transformation_rules


def test_copy_examples_to_directory(tmp_path: Path):
    target_path = tmp_path / "data"

    copy_examples_to_directory(target_path)

    rapport = filecmp.dircmp(target_path, EXAMPLES_DIRECTORY)
    assert not rapport.diff_files
