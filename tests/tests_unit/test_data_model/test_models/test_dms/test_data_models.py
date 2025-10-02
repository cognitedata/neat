from typing import Any

from hypothesis import given, settings

from cognite.neat._data_model.models.dms import DataModelRequest, DataModelResponse

from .strategies import data_model_strategy


class TestDataModelResponse:
    @settings(max_examples=1)
    @given(data_model_strategy())
    def test_as_request(self, data_model: dict[str, Any]) -> None:
        response = DataModelResponse.model_validate(data_model)

        assert isinstance(response, DataModelResponse)

        request = response.as_request()
        assert isinstance(request, DataModelRequest)

        dumped = request.model_dump()
        response_dumped = response.model_dump()
        response_only_keys = set(DataModelResponse.model_fields.keys()) - set(DataModelRequest.model_fields.keys())
        for keys in response_only_keys:
            response_dumped.pop(keys, None)
        assert dumped == response_dumped
