import gzip
import json
from typing import Any

import respx

from cognite.neat._client import NeatClient
from cognite.neat._data_model.models.dms import ViewReference, ViewResponse


class TestViewsAPI:
    def test_list(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_dms_view_response: dict[str, Any]
    ) -> None:
        client = neat_client
        config = client.config
        respx_mock.get(
            config.create_api_url("/models/views"),
        ).respond(
            status_code=200,
            json={
                "items": [example_dms_view_response],
                "nextCursor": None,
            },
        )
        views = client.views.list(
            space="my_space", limit=10, all_versions=True, include_inherited_properties=True, include_global=False
        )
        assert len(views) == 1
        assert views[0].space == "my_space"
        assert views[0].external_id == "MyView"
        assert views[0].version == "v1"
        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]
        assert (
            str(call.request.url.params)
            == "allVersions=true&includeInheritedProperties=true&includeGlobal=false&limit=10&space=my_space"
        )

    def test_list_without_space(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_dms_view_response: dict[str, Any]
    ) -> None:
        client = neat_client
        config = client.config
        respx_mock.get(
            config.create_api_url("/models/views"),
        ).respond(
            status_code=200,
            json={
                "items": [example_dms_view_response],
                "nextCursor": None,
            },
        )
        views = client.views.list(limit=100)
        assert len(views) == 1
        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]
        # Space should not be in params
        assert "space" not in str(call.request.url.params)
        assert "limit=100" in str(call.request.url.params)

    def test_retrieve(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_dms_view_response: dict[str, Any]
    ) -> None:
        client = neat_client
        config = client.config
        respx_mock.post(
            config.create_api_url("/models/views/byids"),
        ).respond(
            status_code=200,
            json={
                "items": [example_dms_view_response],
                "nextCursor": None,
            },
        )
        views = client.views.retrieve(
            items=[
                ViewReference(space="my_space", external_id="MyView", version="v1"),
                ViewReference(space="my_space", external_id="AnotherView", version="v2"),
            ],
            include_inherited_properties=False,
        )
        assert len(views) == 1
        assert views[0].external_id == "MyView"
        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]
        content = call.request.content
        if content.startswith(b"\x1f\x8b"):  # gzip magic number
            content = gzip.decompress(content)
        body = json.loads(content)
        assert len(body["items"]) == 2
        assert body["items"][0] == {"space": "my_space", "externalId": "MyView", "version": "v1"}
        assert body["items"][1] == {"space": "my_space", "externalId": "AnotherView", "version": "v2"}
        assert "includeInheritedProperties=false" in str(call.request.url.params)

    def test_retrieve_empty_list(self, neat_client: NeatClient, respx_mock: respx.MockRouter) -> None:
        client = neat_client
        views = client.views.retrieve(items=[])
        assert len(views) == 0
        assert len(respx_mock.calls) == 0

    def test_apply(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_dms_view_response: dict[str, Any]
    ) -> None:
        client = neat_client
        config = client.config
        respx_mock.post(
            config.create_api_url("/models/views"),
        ).respond(
            status_code=200,
            json={
                "items": [example_dms_view_response],
            },
        )
        response = ViewResponse.model_validate(example_dms_view_response)
        request = response.as_request()
        views = client.views.apply([request])
        assert len(views) == 1
        assert views[0].model_dump() == response.model_dump()
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
            ViewReference(space="my_space", external_id="MyView", version="v1"),
            ViewReference(space="other_space", external_id="OtherView", version="v2"),
        ]
        respx_mock.post(
            config.create_api_url("/models/views/delete"),
        ).respond(
            status_code=200,
            json={
                "items": [item.model_dump(mode="json", by_alias=True) for item in items],
            },
        )
        deleted = client.views.delete(items=items)
        assert deleted == items
        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]

        content = call.request.content
        if content.startswith(b"\x1f\x8b"):  # gzip magic number
            content = gzip.decompress(content)
        body = json.loads(content)
        assert {"items": [item.model_dump(mode="json", by_alias=True) for item in items]} == body
