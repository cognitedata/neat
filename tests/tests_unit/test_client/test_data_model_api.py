from typing import Any

import respx

from cognite.neat._client import NeatClient


class TestDataModelAPI:
    def test_list(
        self, neat_client: NeatClient, respx_mock: respx.MockRouter, example_dms_data_model_response: dict[str, Any]
    ) -> None:
        client = neat_client
        config = client.config
        respx_mock.get(
            config.create_api_url("/models/datamodels"),
        ).respond(
            status_code=200,
            json={
                "items": [example_dms_data_model_response],
                "nextCursor": None,
            },
        )
        models = client.data_models.list(space="my_space", limit=10, all_versions=True, include_global=False)
        assert len(models) == 1
        assert len(respx_mock.calls) == 1
        call = respx_mock.calls[0]
        assert str(call.request.url.params) == "allVersions=true&includeGlobal=false&limit=10&space=my_space"
