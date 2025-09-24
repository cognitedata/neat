import unittest.mock
from typing import Any
from unittest.mock import MagicMock

from cognite.client.exceptions import CogniteAPIError
from requests import Response

from cognite.neat.v0.core._client.testing import monkeypatch_neat_client


class MockPerfCounter:
    def __init__(self):
        self.t = 0

    def increment(self, n):
        self.t += n

    def perf_counter(self):
        return self.t


class TestNeatInstanceAPI:
    def test_408_response_reduce_limit(self):
        clock = MockPerfCounter()
        call_count = 0

        def post_responses(
            url: str,
            json: dict[str, Any],
            params: dict[str, Any] | None = None,
            headers: dict[str, Any] | None = None,
        ) -> Response:
            nonlocal call_count, clock
            call_count += 1
            if call_count == 1:
                raise CogniteAPIError("Request timeout", code=408)
            elif call_count == 2:
                assert "limit" in json
                assert json["limit"] == 500
                cursor = "123"
                clock.increment(60.0)
            elif call_count == 3:
                assert "limit" in json
                assert json["limit"] == int(500 * 1.5)
                cursor = None
            else:
                raise NotImplementedError()
            response = MagicMock(spec=Response)
            response.json.return_value = {"nextCursor": cursor, "items": []}
            return response

        with monkeypatch_neat_client() as client:
            client.post.side_effect = post_responses
            with unittest.mock.patch("time.perf_counter", clock.perf_counter):
                result = list(client.instances.iterate("node"))
        assert not result
