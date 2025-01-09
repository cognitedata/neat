from pathlib import Path

from cognite.neat import NeatSession, get_cognite_client


REPO_ROOT = Path(__file__).resolve().parent.parent
SPACE = "sp_pump_station"


def main() -> None:
    client = get_cognite_client(".env")
    neat = NeatSession(client)
    neat._state.client.loaders.spaces.clean(SPACE)


if __name__ == '__main__':
    main()
