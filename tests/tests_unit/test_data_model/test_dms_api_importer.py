import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import respx
import yaml

from cognite.neat._client import NeatClient
from cognite.neat._data_model.importers import DMSAPIImporter
from cognite.neat._data_model.models.dms import DataModelReference, RequestSchema
from cognite.neat._exceptions import CDFAPIException
from cognite.neat._utils.http_client import FailedRequestMessage


class TestDMSAPIImporter:
    """Test suite for DMSAPIImporter.from_cdf method."""

    def test_from_cdf_success(
        self,
        neat_client: NeatClient,
        respx_mock_data_model: respx.MockRouter,
    ) -> None:
        """Test successful import of a data model from CDF with all dependencies."""
        # Create the importer
        data_model_ref = DataModelReference(space="my_space", external_id="my_data_model", version="v1")
        importer = DMSAPIImporter.from_cdf(data_model_ref, neat_client)

        # Validate the importer was created
        assert isinstance(importer, DMSAPIImporter)

        # Validate the schema
        schema = importer.to_data_model()
        assert isinstance(schema, RequestSchema)
        assert schema.data_model.space == "my_space"
        assert schema.data_model.external_id == "my_data_model"
        assert schema.data_model.version == "v1"
        assert len(schema.views) == 1
        assert schema.views[0].space == "my_space"
        assert schema.views[0].external_id == "MyView"
        assert len(schema.containers) == 1
        assert schema.containers[0].space == "my_space"
        assert schema.containers[0].external_id == "MyContainer"
        assert len(schema.spaces) == 1
        assert schema.spaces[0].space == "my_space"

        # Verify all expected API calls were made
        assert len(respx_mock_data_model.calls) == 4

    def test_from_cdf_data_model_not_found(
        self,
        neat_client: NeatClient,
        respx_mock: respx.MockRouter,
    ) -> None:
        """Test that CDFAPIException is raised when data model is not found."""
        config = neat_client.config

        # Mock data model retrieval returning empty
        respx_mock.post(config.create_api_url("/models/datamodels/byids")).respond(
            status_code=200,
            json={"items": []},
        )
        respx_mock.get(
            config.create_api_url("/models/datamodels?allVersions=false&includeGlobal=true&limit=1000")
        ).respond(
            status_code=200,
            json={"items": []},
        )

        data_model_ref = DataModelReference(space="my_space", external_id="missing_model", version="v1")

        with pytest.raises(CDFAPIException) as exc_info:
            DMSAPIImporter.from_cdf(data_model_ref, neat_client)

        assert len(exc_info.value.messages) == 1
        request_message = exc_info.value.messages[0]
        assert isinstance(request_message, FailedRequestMessage)
        error_message = request_message.message
        assert "not found in CDF" in error_message
        assert len(respx_mock.calls) == 2, (
            "Expected two API calls to be made. One for data model and one for listing available models."
        )
        user_message = str(exc_info.value)
        assert "my_space:missing_model(version=v1)" in user_message

    def test_from_cdf_missing_views(
        self,
        neat_client: NeatClient,
        respx_mock: respx.MockRouter,
        example_dms_data_model_response: dict[str, Any],
    ) -> None:
        """Test that CDFAPIException is raised when views referenced by data model are missing."""
        config = neat_client.config

        # Mock data model retrieval
        respx_mock.post(config.create_api_url("/models/datamodels/byids")).respond(
            status_code=200,
            json={"items": [example_dms_data_model_response]},
        )

        # Mock views retrieval returning empty (views not found)
        respx_mock.post(config.create_api_url("/models/views/byids")).respond(
            status_code=200,
            json={"items": []},
        )

        data_model_ref = DataModelReference(space="my_space", external_id="my_data_model", version="v1")

        with pytest.raises(CDFAPIException) as exc_info:
            DMSAPIImporter.from_cdf(data_model_ref, neat_client)

        assert len(exc_info.value.messages) == 1
        request_message = exc_info.value.messages[0]
        assert isinstance(request_message, FailedRequestMessage)
        error_message = request_message.message
        assert "Views" in error_message
        assert "not found in CDF" in error_message
        assert len(respx_mock.calls) == 2

    def test_from_cdf_missing_containers(
        self,
        neat_client: NeatClient,
        respx_mock: respx.MockRouter,
        example_dms_data_model_response: dict[str, Any],
        example_dms_view_response: dict[str, Any],
    ) -> None:
        """Test that CDFAPIException is raised when containers referenced by views are missing."""
        config = neat_client.config

        # Mock data model retrieval
        respx_mock.post(config.create_api_url("/models/datamodels/byids")).respond(
            status_code=200,
            json={"items": [example_dms_data_model_response]},
        )

        # Mock views retrieval
        respx_mock.post(config.create_api_url("/models/views/byids")).respond(
            status_code=200,
            json={"items": [example_dms_view_response]},
        )

        # Mock containers retrieval returning empty (containers not found)
        respx_mock.post(config.create_api_url("/models/containers/byids")).respond(
            status_code=200,
            json={"items": []},
        )

        data_model_ref = DataModelReference(space="my_space", external_id="my_data_model", version="v1")

        with pytest.raises(CDFAPIException) as exc_info:
            DMSAPIImporter.from_cdf(data_model_ref, neat_client)

        assert len(exc_info.value.messages) == 1
        request_message = exc_info.value.messages[0]
        assert isinstance(request_message, FailedRequestMessage)
        error_message = request_message.message
        assert "not found in CDF" in error_message
        assert len(respx_mock.calls) == 3

    def test_from_cdf_missing_spaces(
        self,
        neat_client: NeatClient,
        respx_mock: respx.MockRouter,
        example_dms_data_model_response: dict[str, Any],
        example_dms_view_response: dict[str, Any],
        example_dms_container_response: dict[str, Any],
    ) -> None:
        """Test that CDFAPIException is raised when spaces are missing."""
        config = neat_client.config

        # Mock data model retrieval
        respx_mock.post(config.create_api_url("/models/datamodels/byids")).respond(
            status_code=200,
            json={"items": [example_dms_data_model_response]},
        )

        # Mock views retrieval
        respx_mock.post(config.create_api_url("/models/views/byids")).respond(
            status_code=200,
            json={"items": [example_dms_view_response]},
        )

        # Mock containers retrieval
        respx_mock.post(config.create_api_url("/models/containers/byids")).respond(
            status_code=200,
            json={"items": [example_dms_container_response]},
        )

        # Mock spaces retrieval returning empty (spaces not found)
        respx_mock.post(config.create_api_url("/models/spaces/byids")).respond(
            status_code=200,
            json={"items": []},
        )

        data_model_ref = DataModelReference(space="my_space", external_id="my_data_model", version="v1")

        with pytest.raises(CDFAPIException) as exc_info:
            DMSAPIImporter.from_cdf(data_model_ref, neat_client)

        assert len(exc_info.value.messages) == 1
        request_message = exc_info.value.messages[0]
        assert isinstance(request_message, FailedRequestMessage)
        error_message = request_message.message
        assert "Spaces" in error_message
        assert "not found in CDF" in error_message
        assert len(respx_mock.calls) == 4

    def test_read_from_single_yaml_file(self, example_dms_schema_request: dict[str, Any]) -> None:
        """Test reading data model schema from a single YAML file."""
        yaml_file = MagicMock(spec=Path)
        yaml_file.read_text.return_value = yaml.safe_dump(example_dms_schema_request)
        yaml_file.suffix = ".yaml"

        importer = DMSAPIImporter.from_yaml(yaml_file)
        schema = importer.to_data_model()
        assert schema.model_dump(by_alias=True, exclude_unset=True) == example_dms_schema_request

    def test_read_from_single_json_file(self, example_dms_schema_request: dict[str, Any]) -> None:
        """Test reading data model schema from a single JSON file."""
        json_file = MagicMock(spec=Path)
        json_file.read_text.return_value = json.dumps(example_dms_schema_request)
        json_file.suffix = ".json"

        importer = DMSAPIImporter.from_yaml(json_file)
        schema = importer.to_data_model()
        assert schema.model_dump(by_alias=True, exclude_unset=True) == example_dms_schema_request

    def test_read_multi_yaml_directory(self, example_dms_schema_request: dict[str, Any]) -> None:
        """Test reading data model schema from multiple YAML files in a directory."""
        yaml_files: list[MagicMock] = []
        for key, data in example_dms_schema_request.items():
            yaml_file = MagicMock(spec=Path)
            yaml_file.read_text.return_value = yaml.safe_dump(data)
            yaml_file.suffix = ".yaml"
            yaml_file.stem = f"my.{key.removesuffix('s')}"
            yaml_files.append(yaml_file)
        yaml_dir = MagicMock(spec=Path)
        yaml_dir.rglob.return_value = yaml_files

        importer = DMSAPIImporter.from_yaml(yaml_dir)
        schema = importer.to_data_model()
        assert schema.model_dump(by_alias=True, exclude_unset=True) == example_dms_schema_request
