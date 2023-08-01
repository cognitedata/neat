# from pathlib import Path
import pytest
from cognite.client.testing import monkeypatch_cognite_client

from cognite.neat.config import copy_examples_to_directory
from cognite.neat.workflows import WorkflowManager


@pytest.mark.skip("In development")
def test_default_neat_workflow(tmp_path, data_regression):
    copy_examples_to_directory(tmp_path)
    with monkeypatch_cognite_client() as client:
        manager = WorkflowManager(
            client,
            registry_storage_type="file",
            workflows_storage_path=tmp_path / "workflows",
            rules_storage_path=tmp_path / "rules",
            data_store_path=tmp_path,
            data_set_id=0,
        )
        manager.load_workflows_from_storage()
        result = manager.start_workflow("default", sync=True)

    assert result
