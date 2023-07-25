import logging
from pathlib import Path

from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat.constants import EXAMPLE_RULES, EXAMPLE_WORKFLOWS, PACKAGE_DIRECTORY
from cognite.neat.workflows.workflow import WorkflowManager

ROOT = Path(__file__).resolve().parent.parent


logging.basicConfig(level=logging.INFO)


def main():
    with monkeypatch_cognite_client() as client:
        manager = WorkflowManager(
            client,
            registry_storage_type="file",
            workflows_storage_path=EXAMPLE_WORKFLOWS,
            rules_storage_path=EXAMPLE_RULES,
            data_storage_path=PACKAGE_DIRECTORY,
            data_set_id=0,
        )
        manager.load_workflows_from_storage_v2()
        result = manager.start_workflow("default", sync=True)

    print(result)


if __name__ == "__main__":
    main()
