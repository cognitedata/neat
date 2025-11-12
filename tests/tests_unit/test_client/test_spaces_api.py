import gzip
import json
from typing import Any

import respx

from cognite.neat._client import NeatClient
from cognite.neat._data_model.models.dms import SpaceReference, SpaceResponse


class TestSpacesAPI:
    def test_list(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_dms_space_response: dict[str, Any]
    ) -> None:
        client = neat_client
        config = client.config
        respx_mock.get(
            config.create_api_url("/models/spaces"),
        ).respond(
            status_code=200,
            json={
                "items": [example_dms_space_response],
                "nextCursor": None,
            },
        )
        spaces = client.spaces.list(limit=100, include_global=False)
        assert len(spaces) == 1
        assert spaces[0].space == "my_space"
        assert spaces[0].name == "My Space"
        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]
        assert str(call.request.url.params) == "includeGlobal=false&limit=100"

    def test_list_with_global(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_dms_space_response: dict[str, Any]
    ) -> None:
        client = neat_client
        config = client.config
        respx_mock.get(
            config.create_api_url("/models/spaces"),
        ).respond(
            status_code=200,
            json={
                "items": [example_dms_space_response],
                "nextCursor": None,
            },
        )
        spaces = client.spaces.list(include_global=True)
        assert len(spaces) == 1
        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]
        assert "includeGlobal=true" in str(call.request.url.params)

    def test_retrieve(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_dms_space_response: dict[str, Any]
    ) -> None:
        client = neat_client
        config = client.config
        respx_mock.post(
            config.create_api_url("/models/spaces/byids"),
        ).respond(
            status_code=200,
            json={
                "items": [example_dms_space_response],
                "nextCursor": None,
            },
        )
        spaces = client.spaces.retrieve(
            spaces=[SpaceReference(space=space) for space in ["my_space", "other_space", "third_space"]]
        )
        assert len(spaces) == 1
        assert spaces[0].space == "my_space"
        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]
        content = call.request.content
        if content.startswith(b"\x1f\x8b"):  # gzip magic number
            content = gzip.decompress(content)
        body = json.loads(content)
        assert len(body["items"]) == 3
        assert body["items"][0] == {"space": "my_space"}
        assert body["items"][1] == {"space": "other_space"}
        assert body["items"][2] == {"space": "third_space"}

    def test_retrieve_empty_list(self, neat_client: NeatClient, respx_mock: respx.MockRouter) -> None:
        client = neat_client
        spaces = client.spaces.retrieve(spaces=[])
        assert len(spaces) == 0
        assert len(respx_mock.calls) == 0

    def test_apply(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_dms_space_response: dict[str, Any]
    ) -> None:
        client = neat_client
        config = client.config
        respx_mock.post(
            config.create_api_url("/models/spaces"),
        ).respond(
            status_code=200,
            json={
                "items": [example_dms_space_response],
            },
        )
        response = SpaceResponse.model_validate(example_dms_space_response)
        request = response.as_request()
        spaces = client.spaces.apply([request])
        assert len(spaces) == 1
        assert spaces[0].model_dump() == response.model_dump()
        call = respx_mock.calls[0]

        content = call.request.content
        if content.startswith(b"\x1f\x8b"):  # gzip magic number
            content = gzip.decompress(content)
        body = json.loads(content)
        assert {"items": [request.model_dump(mode="json", by_alias=True)]} == body

    def test_delete(self, neat_client: NeatClient, respx_mock: respx.MockRouter) -> None:
        client = neat_client
        config = client.config
        items = [
            SpaceReference(space="my_space"),
            SpaceReference(space="other_space"),
        ]
        respx_mock.post(
            config.create_api_url("/models/spaces/delete"),
        ).respond(
            status_code=200,
            json={
                "items": [item.model_dump(mode="json", by_alias=True) for item in items],
            },
        )
        deleted = client.spaces.delete(spaces=items)
        assert deleted == items
        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]

        content = call.request.content
        if content.startswith(b"\x1f\x8b"):  # gzip magic number
            content = gzip.decompress(content)
        body = json.loads(content)
        assert {"items": [item.model_dump(mode="json", by_alias=True) for item in items]} == body
