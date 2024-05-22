from cognite.neat.config import Config
from pathlib import Path

from cognite.neat.utils.utils import get_cognite_client_from_config
from cognite.neat.utils.cdf import clean_space


REPO_ROOT = Path(__file__).resolve().parent.parent
SPACE = "aleks_playground_2"


def main() -> None:
    config = Config.from_yaml(REPO_ROOT / "config.yaml")
    client = get_cognite_client_from_config(config.cdf_client)

    clean_space(client, SPACE)


if __name__ == '__main__':
    main()
