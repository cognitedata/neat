from cognite.neat.config import Config
from pathlib import Path


from cognite.neat.utils.cdf import clean_space


REPO_ROOT = Path(__file__).resolve().parent.parent
SPACE = "sp_pump_station"


def main() -> None:
    config = Config.from_yaml(REPO_ROOT / "config.yaml")
    client = config.cdf_auth_config.get_client()

    clean_space(client, SPACE)


if __name__ == '__main__':
    main()
