import filecmp
from pathlib import Path

from cognite.neat.config import Config, copy_examples_to_directory
from cognite.neat.constants import EXAMPLE_GRAPHS, EXAMPLE_RULES, EXAMPLE_WORKFLOWS
from cognite.neat.legacy.rules.models.rules import Rules


def test_load_excel(transformation_rules: Rules):
    assert transformation_rules


def test_copy_examples_to_directory(tmp_path: Path):
    target_path = tmp_path / "data"
    config = Config(
        data_store_path=target_path,
    )
    copy_examples_to_directory(config)

    rapport = filecmp.dircmp(config.rules_store_path, EXAMPLE_RULES)
    assert not rapport.diff_files

    rapport = filecmp.dircmp(config.source_graph_path, EXAMPLE_GRAPHS)
    assert not rapport.diff_files

    rapport = filecmp.dircmp(config.workflows_store_path, EXAMPLE_WORKFLOWS)
    assert not rapport.diff_files
