import logging
from pathlib import Path

from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat._constants import PACKAGE_DIRECTORY
from cognite.neat._workflows import WorkflowManager
from cognite.neat._config import Config, WorkflowsStoreType

ROOT = Path(__file__).resolve().parent.parent


logging.basicConfig(level=logging.INFO)


def main():
    with monkeypatch_cognite_client() as client:
        config = Config(
            workflows_store_type=WorkflowsStoreType.FILE,
            data_store_path=PACKAGE_DIRECTORY / "legacy",
            cdf_default_dataset_id=0,
        )

        manager = WorkflowManager(
            client,
            config,
        )
        manager.load_workflows_from_storage()
        result = manager.start_workflow("default", sync=True)

    print(result)


if __name__ == "__main__":
    main()
