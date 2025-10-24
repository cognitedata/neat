import gzip
import json
from typing import Any

import respx

from cognite.neat._client import NeatClient
from cognite.neat._data_model.models.dms import ContainerReference


class TestContainersAPI:
    def test_list(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_dms_container_response: dict[str, Any]
    ) -> None:
        client = neat_client
        config = client.config
        respx_mock.get(
            config.create_api_url("/models/containers"),
        ).respond(
            status_code=200,
            json={
                "items": [example_dms_container_response],
                "nextCursor": None,
            },
        )
        containers = client.containers.list(space="my_space", limit=50, include_global=True)
        assert len(containers) == 1
        assert containers[0].space == "my_space"
        assert containers[0].external_id == "MyContainer"
        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]
        assert str(call.request.url.params) == "includeGlobal=true&limit=50&space=my_space"

    def test_list_without_space(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_dms_container_response: dict[str, Any]
    ) -> None:
        client = neat_client
        config = client.config
        respx_mock.get(
            config.create_api_url("/models/containers"),
        ).respond(
            status_code=200,
            json={
                "items": [example_dms_container_response],
                "nextCursor": None,
            },
        )
        containers = client.containers.list(limit=25)
        assert len(containers) == 1
        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]
        # Space should not be in params
        assert "space" not in str(call.request.url.params)
        assert "limit=25" in str(call.request.url.params)

    def test_retrieve(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_dms_container_response: dict[str, Any]
    ) -> None:
        client = neat_client
        config = client.config
        respx_mock.post(
            config.create_api_url("/models/containers/byids"),
        ).respond(
            status_code=200,
            json={
                "items": [example_dms_container_response],
                "nextCursor": None,
            },
        )
        containers = client.containers.retrieve(
            items=[
                ContainerReference(space="my_space", external_id="MyContainer"),
                ContainerReference(space="other_space", external_id="OtherContainer"),
            ],
        )
        assert len(containers) == 1
        assert containers[0].external_id == "MyContainer"
        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]

        content = call.request.content
        if content.startswith(b"\x1f\x8b"):  # gzip magic number
            content = gzip.decompress(content)
        body = json.loads(content)
        assert len(body["items"]) == 2
        assert body["items"][0] == {"space": "my_space", "externalId": "MyContainer"}
        assert body["items"][1] == {"space": "other_space", "externalId": "OtherContainer"}

    def test_retrieve_empty_list(self, neat_client: NeatClient, respx_mock: respx.MockRouter) -> None:
        client = neat_client
        containers = client.containers.retrieve(items=[])
        assert len(containers) == 0
        assert len(respx_mock.calls) == 0
