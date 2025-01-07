from cognite.neat._config import Config
from pathlib import Path

from cognite.neat._client import NeatClient


REPO_ROOT = Path(__file__).resolve().parent.parent
SPACE = "sp_pump_station"


def main() -> None:
    config = Config.from_yaml(REPO_ROOT / "config.yaml")
    client = config.cdf_auth_config.get_client()
    client.files.list()

    neat_client = NeatClient(client)
    neat_client.loaders.spaces.clean(SPACE)


if __name__ == '__main__':
    main()
