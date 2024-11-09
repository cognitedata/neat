from cognite.client import CogniteClient

ENVIRONMENT_VARIABLE = "NEAT_ENGINE"


def load_neat_engine(client: CogniteClient | None = None) -> str:
    raise NotImplementedError()
