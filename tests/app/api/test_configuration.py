from pathlib import Path

from cognite.neat.app.api.configuration import Config


def test_dump_and_load_default_config(tmp_path: Path):
    config = Config()
    filepath = tmp_path / "tmp_config.yaml"

    config.to_yaml(filepath)

    loaded_config = config.from_yaml(filepath)

    assert config == loaded_config
