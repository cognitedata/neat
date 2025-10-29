import json
from collections import Counter
from collections.abc import Iterator
from unittest.mock import patch

import httpx
import pytest
import respx
from cognite.client import ClientConfig, global_config
from cognite.client.credentials import Token

from cognite.neat._utils.http_client import (
    ErrorDetails,
    FailedRequestItems,
    FailedRequestMessage,
    FailedResponse,
    FailedResponseItems,
    HTTPClient,
    ItemIDBody,
    ItemMessage,
    ItemsRequest,
    ParametersRequest,
    SimpleBodyRequest,
    SuccessResponse,
    SuccessResponseItems,
)
from cognite.neat._utils.useful_types import ReferenceObject

BASE_URL = "http://my_cluster.cognitedata.com"


@pytest.fixture
def rsps() -> Iterator[respx.MockRouter]:
    with respx.mock() as rsps:
        yield rsps


@pytest.fixture
def client_config() -> ClientConfig:
    return ClientConfig(
        client_name="test-client",
        project="test-project",
        base_url=BASE_URL,
        max_workers=1,
        timeout=10,
        credentials=Token("abc"),
    )


@pytest.fixture
def disable_gzip() -> Iterator[None]:
    old = global_config.disable_gzip
    global_config.disable_gzip = True
    yield
    global_config.disable_gzip = old


@pytest.fixture
def disable_pypi_check() -> Iterator[None]:
    old = global_config.disable_pypi_version_check
    global_config.disable_pypi_version_check = True
    yield
    global_config.disable_pypi_version_check = old


@pytest.fixture
def http_client(client_config: ClientConfig) -> Iterator[HTTPClient]:
    with HTTPClient(client_config) as client:
        yield client


@pytest.fixture
def http_client_one_retry(client_config: ClientConfig) -> Iterator[HTTPClient]:
    with HTTPClient(client_config, max_retries=1) as client:
        yield client


@pytest.mark.usefixtures("disable_pypi_check")
class TestHTTPClient:
    def test_get_request(self, rsps: respx.MockRouter, http_client: HTTPClient) -> None:
        rsps.get("https://example.com/api/resource").respond(json={"key": "value"}, status_code=200)
        results = http_client.request(
            ParametersRequest(
                endpoint_url="https://example.com/api/resource", method="GET", parameters={"query": "test"}
            )
        )
        assert len(results) == 1
        response = results[0]
        assert isinstance(response, SuccessResponse)
        assert response.code == 200
        assert response.body == '{"key":"value"}'
        assert rsps.calls[-1].request.url == "https://example.com/api/resource?query=test"

    @pytest.mark.usefixtures("disable_gzip")
    def test_post_request(self, rsps: respx.MockRouter, http_client: HTTPClient) -> None:
        rsps.post("https://example.com/api/resource").respond(json={"id": 123, "status": "created"}, status_code=201)
        results = http_client.request(
            SimpleBodyRequest(
                endpoint_url="https://example.com/api/resource",
                method="POST",
                body=json.dumps({"name": "new resource"}),
            )
        )
        assert len(results) == 1
        response = results[0]
        assert isinstance(response, SuccessResponse)
        assert response.code == 201
        assert response.body == '{"id":123,"status":"created"}'
        assert rsps.calls[-1].request.content == json.dumps({"name": "new resource"}).encode()

    def test_failed_request(self, rsps: respx.MockRouter, http_client: HTTPClient) -> None:
        rsps.get("https://example.com/api/resource").respond(
            json={"error": {"code": 400, "message": "bad request"}}, status_code=400
        )
        results = http_client.request(
            ParametersRequest(
                endpoint_url="https://example.com/api/resource", method="GET", parameters={"query": "fail"}
            )
        )
        assert len(results) == 1
        response = results[0]
        assert isinstance(response, FailedResponse)
        assert response.code == 400
        assert response.error.message == "bad request"

    @pytest.mark.usefixtures("disable_gzip")
    def test_retry_then_success(self, rsps: respx.MockRouter, http_client: HTTPClient) -> None:
        url = "https://example.com/api/resource"
        rsps.get(url).respond(json={"error": "service unavailable"}, status_code=503)
        rsps.get(url).respond(json={"key": "value"}, status_code=200)
        results = http_client.request_with_retries(ParametersRequest(endpoint_url=url, method="GET"))
        assert len(results) == 1
        response = results[0]
        assert isinstance(response, SuccessResponse)
        assert response.code == 200
        assert response.body == '{"key":"value"}'

    def test_retry_exhausted(self, http_client_one_retry: HTTPClient, rsps: respx.MockRouter) -> None:
        client = http_client_one_retry
        for _ in range(2):
            rsps.get("https://example.com/api/resource").respond(
                json={"error": {"message": "service unavailable", "code": 503}}, status_code=503
            )
        with patch("time.sleep"):  # Patch sleep to speed up the test
            results = client.request_with_retries(
                ParametersRequest(endpoint_url="https://example.com/api/resource", method="GET")
            )

        assert len(results) == 1
        response = results[0]
        assert isinstance(response, FailedResponse)
        assert response.code == 503
        assert response.error.message == "service unavailable"

    def test_connection_error(self, http_client_one_retry: HTTPClient, rsps: respx.MockRouter) -> None:
        http_client = http_client_one_retry
        rsps.get("http://nonexistent.domain/api/resource").mock(
            side_effect=httpx.ConnectError("Simulated connection error")
        )
        with patch("time.sleep"):  # Patch sleep to speed up the test
            results = http_client.request_with_retries(
                ParametersRequest(endpoint_url="http://nonexistent.domain/api/resource", method="GET")
            )
        response = results[0]
        assert len(results) == 1
        assert isinstance(response, FailedRequestMessage)
        assert "RequestException after 1 attempts (connect error): Simulated connection error" == response.message

    def test_read_timeout_error(self, http_client_one_retry: HTTPClient, rsps: respx.MockRouter) -> None:
        http_client = http_client_one_retry
        rsps.get("https://example.com/api/resource").mock(side_effect=httpx.ReadTimeout("Simulated read timeout"))
        bad_request = ParametersRequest(endpoint_url="https://example.com/api/resource", method="GET")
        with patch("time.sleep"):  # Patch sleep to speed up the test
            results = http_client.request_with_retries(bad_request)
        response = results[0]
        assert len(results) == 1
        assert isinstance(response, FailedRequestMessage)
        assert "RequestException after 1 attempts (read error): Simulated read timeout" == response.message

    def test_zero_retries(self, client_config: ClientConfig, rsps: respx.MockRouter) -> None:
        client = HTTPClient(client_config, max_retries=0)
        rsps.get("https://example.com/api/resource").respond(
            json={"error": {"message": "service unavailable", "code": 503}}, status_code=503
        )
        results = client.request_with_retries(
            ParametersRequest(endpoint_url="https://example.com/api/resource", method="GET")
        )
        assert len(results) == 1
        response = results[0]
        assert isinstance(response, FailedResponse)
        assert response.code == 503
        assert response.error.message == "service unavailable"
        assert len(rsps.calls) == 1

    def test_raise_if_already_retied(self, http_client_one_retry: HTTPClient) -> None:
        http_client = http_client_one_retry
        bad_request = ParametersRequest(endpoint_url="https://example.com/api/resource", method="GET", status_attempt=3)
        with pytest.raises(RuntimeError, match=r"RequestMessage has already been attempted 3 times."):
            http_client.request_with_retries(bad_request)

    def test_request_alpha(self, http_client: HTTPClient, rsps: respx.MockRouter) -> None:
        rsps.get("https://example.com/api/alpha/endpoint").respond(json={"key": "value"}, status_code=200)
        results = http_client.request(
            ParametersRequest(
                endpoint_url="https://example.com/api/alpha/endpoint",
                method="GET",
                parameters={"query": "test"},
                api_version="alpha",
            )
        )
        assert len(results) == 1
        response = results[0]
        assert isinstance(response, SuccessResponse)
        assert response.code == 200
        assert rsps.calls[-1].request.headers["cdf-version"] == "alpha"

    def test_unexpected_error_format(self, http_client: HTTPClient, rsps: respx.MockRouter) -> None:
        rsps.get("https://example.com/api/resource").respond(
            json={"unexpected_error": "Something went wrong"}, status_code=500
        )
        results = http_client.request(ParametersRequest(endpoint_url="https://example.com/api/resource", method="GET"))
        assert len(results) == 1
        response = results[0]
        assert isinstance(response, FailedResponse)
        assert response.code == 500
        assert response.error.message == '{"unexpected_error":"Something went wrong"}'


class MyReference(ReferenceObject):
    id: str


@pytest.mark.usefixtures("disable_pypi_check")
class TestHTTPClientItemRequests:
    @pytest.mark.usefixtures("disable_gzip")
    def test_request_with_items_happy_path(self, http_client: HTTPClient, rsps: respx.MockRouter) -> None:
        rsps.post("https://example.com/api/resource").respond(
            json={"items": [{"id": 1, "value": 42}, {"id": 2, "value": 43}]},
            status_code=200,
        )
        items = [MyReference(id="1"), MyReference(id="2")]
        results = http_client.request(
            ItemsRequest(
                endpoint_url="https://example.com/api/resource",
                method="POST",
                body=ItemIDBody(items=items, extra_args={"autoCreateDirectRelations": True}),
            )
        )
        assert len(results) == 1
        response = results[0]
        assert isinstance(response, SuccessResponseItems)
        assert response.code == 200
        assert response.body == '{"items":[{"id":1,"value":42},{"id":2,"value":43}]}'
        assert response.ids == items
        assert len(rsps.calls) == 1
        assert json.loads(rsps.calls[0].request.content) == {
            "autoCreateDirectRelations": True,
            "items": [{"id": "1"}, {"id": "2"}],
        }

    @pytest.mark.usefixtures("disable_gzip")
    def test_request_with_items_issues(self, http_client: HTTPClient, rsps: respx.MockRouter) -> None:
        def server_callback(request: httpx.Request) -> httpx.Response:
            # Check request body content
            body_content = request.content.decode() if request.content else ""
            if "fail" in body_content:
                return httpx.Response(400, json={"error": {"message": "Item failed", "code": 400}})
            elif "success" in body_content:
                return httpx.Response(200, json={"items": {"externalId": "success", "value": 123}})
            else:
                return httpx.Response(200, json={"items": []})

        rsps.post("https://example.com/api/resource").mock(side_effect=server_callback)

        items = [MyReference(id="success"), MyReference(id="fail")]
        results = http_client.request_with_retries(
            ItemsRequest(
                endpoint_url="https://example.com/api/resource",
                method="POST",
                body=ItemIDBody(items=items, extra_args={"autoCreateDirectRelations": True}),
            )
        )
        assert len(results) == 2
        first, second = results
        assert isinstance(first, SuccessResponseItems)
        assert first.body == '{"items":{"externalId":"success","value":123}}'
        assert first.ids == items[:1]
        assert isinstance(second, FailedResponseItems)
        assert second.code == 400
        assert second.error.message == "Item failed"
        assert second.ids == items[1:]

        assert len(rsps.calls) == 3  # Three requests made
        first, second, third = rsps.calls
        # First call will fail, and split into 1 item + 1 items
        assert json.loads(first.request.content) == {
            "items": [{"id": "success"}, {"id": "fail"}],
            "autoCreateDirectRelations": True,
        }
        # Second succeeds with 1 item.
        assert json.loads(second.request.content) == {"items": [{"id": "success"}], "autoCreateDirectRelations": True}
        # Third fails with 1 item.
        assert json.loads(third.request.content) == {"items": [{"id": "fail"}], "autoCreateDirectRelations": True}

    def test_request_all_item_fail(self, http_client: HTTPClient, rsps: respx.MockRouter) -> None:
        rsps.post("https://example.com/api/resource").respond(
            json={"error": {"message": "Unauthorized", "code": 401}},
            status_code=401,
        )
        items = [MyReference(id="1"), MyReference(id="2")]
        results = http_client.request(
            ItemsRequest(
                endpoint_url="https://example.com/api/resource",
                method="POST",
                body=ItemIDBody(items=items),
            )
        )
        assert results == [
            FailedResponseItems(
                code=401,
                error=ErrorDetails(message="Unauthorized", code=401),
                ids=items,
                body='{"error":{"message":"Unauthorized","code":401}}',
            )
        ]
        assert len(rsps.calls) == 1  # Only one request made

    def test_request_no_items_response(self, http_client: HTTPClient, rsps: respx.MockRouter) -> None:
        rsps.post("https://example.com/api/resource/delete").respond(status_code=200)
        items = [MyReference(id="1"), MyReference(id="2")]
        results = http_client.request(
            ItemsRequest(
                endpoint_url="https://example.com/api/resource/delete",
                method="POST",
                body=ItemIDBody(items=items),
            )
        )
        assert len(results) == 1
        response = results[0]
        assert isinstance(response, SuccessResponseItems)
        assert response.code == 200
        assert response.body == ""
        assert response.ids == items

    def test_timeout_error(self, http_client_one_retry: HTTPClient, rsps: respx.MockRouter) -> None:
        client = http_client_one_retry
        rsps.post("https://example.com/api/resource").mock(side_effect=httpx.ReadTimeout("Simulated timeout error"))
        items = [MyReference(id="1")]
        with patch("time.sleep"):
            results = client.request_with_retries(
                ItemsRequest(
                    endpoint_url="https://example.com/api/resource",
                    method="POST",
                    body=ItemIDBody(items=items),
                )
            )
        assert len(results) == 1
        response = results[0]
        assert isinstance(response, FailedRequestItems)
        assert response.ids == items
        assert "RequestException after 1 attempts (read error): Simulated timeout error" == response.message

    @pytest.mark.usefixtures("disable_gzip")
    def test_early_failure(self, http_client_one_retry: HTTPClient, rsps: respx.MockRouter) -> None:
        client = http_client_one_retry
        rsps.post("https://example.com/api/resource").respond(
            json={"error": {"message": "Server error", "code": 400}},
            status_code=400,
        )
        items = [MyReference(id=str(i)) for i in range(1000)]
        with patch("time.sleep"):
            results = client.request_with_retries(
                ItemsRequest(
                    endpoint_url="https://example.com/api/resource",
                    method="POST",
                    body=ItemIDBody(items=items),
                    max_failures_before_abort=5,
                )
            )
        assert len(rsps.calls) == 5
        actual_items_per_request = [len(json.loads(call.request.content)["items"]) for call in rsps.calls]
        assert actual_items_per_request == [1000, 500, 500, 250, 250]  # Splits in half each time
        item_messages = [msg for msg in results if isinstance(msg, ItemMessage)]
        assert len(item_messages) == len(results)
        failures = Counter([type(message) for message in item_messages for _ in message.ids])
        assert failures == {
            FailedResponseItems: 250,  # 250 items keeps the original error message.
            FailedRequestItems: 750,  # 750 items get the early abort message.
        }

    @pytest.mark.usefixtures("disable_gzip")
    def test_abort_on_first_failure(self, http_client: HTTPClient, rsps: respx.MockRouter) -> None:
        client = http_client
        rsps.post("https://example.com/api/resource").respond(
            json={"error": {"message": "Server error", "code": 400}},
            status_code=400,
        )
        items = [MyReference(id=str(i)) for i in range(1000)]
        results = client.request_with_retries(
            ItemsRequest(
                endpoint_url="https://example.com/api/resource",
                method="POST",
                body=ItemIDBody(items=items),
                max_failures_before_abort=1,
            )
        )

        actual_failure_types = Counter(
            [type(message) for message in results if isinstance(message, ItemMessage) for _ in message.ids]
        )
        assert actual_failure_types == {FailedResponseItems: 1000}
        assert len(rsps.calls) == 1
        actual_items_per_request = [len(json.loads(call.request.content)["items"]) for call in rsps.calls]
        assert actual_items_per_request == [1000]

    @pytest.mark.usefixtures("disable_gzip")
    def test_abort_on_second_failure(self, http_client: HTTPClient, rsps: respx.MockRouter) -> None:
        client = http_client
        rsps.post("https://example.com/api/resource").respond(
            json={"error": {"message": "Server error", "code": 400}},
            status_code=400,
        )
        items = [MyReference(id=str(i)) for i in range(1000)]
        results = client.request_with_retries(
            ItemsRequest(
                endpoint_url="https://example.com/api/resource",
                method="POST",
                body=ItemIDBody(items=items),
                max_failures_before_abort=2,
            )
        )
        actual_failure_types = Counter(
            [type(message) for message in results if isinstance(message, ItemMessage) for _ in message.ids]
        )
        assert actual_failure_types == {FailedResponseItems: 500, FailedRequestItems: 500}
        assert len(rsps.calls) == 2
        actual_items_per_request = [len(json.loads(call.request.content)["items"]) for call in rsps.calls]
        assert actual_items_per_request == [1000, 500]

    @pytest.mark.usefixtures("disable_gzip")
    def test_never_abort_on_failure(self, http_client: HTTPClient, rsps: respx.MockRouter) -> None:
        client = http_client
        rsps.post("https://example.com/api/resource").respond(
            json={"error": {"message": "Server error", "code": 400}},
            status_code=400,
        )
        items = [MyReference(id=str(i)) for i in range(100)]
        results = client.request_with_retries(
            ItemsRequest(
                endpoint_url="https://example.com/api/resource",
                method="POST",
                body=ItemIDBody(items=items),
                max_failures_before_abort=-1,  # Never abort
            )
        )
        actual_failure_types = Counter(
            [type(message) for message in results if isinstance(message, ItemMessage) for _ in message.ids]
        )
        assert actual_failure_types == {FailedResponseItems: 100}
        assert len(rsps.calls) == 199

    @pytest.mark.usefixtures("disable_gzip")
    def test_failing_3_items(self, http_client_one_retry: HTTPClient, rsps: respx.MockRouter) -> None:
        client = http_client_one_retry

        def dislike_942_112_and_547(request: httpx.Request) -> httpx.Response:
            # Check request body content
            body_content = request.content.decode() if request.content else ""
            for no in ["942", "112", "547"]:
                if no in body_content:
                    return httpx.Response(400, json={"error": {"message": f"Item {no} is not allowed", "code": 400}})

            # Parse the request body to create response items
            try:
                body_data = json.loads(body_content)
                items = body_data.get("items", [])
                response_items = [{"id": item["id"], "status": "ok"} for item in items]
                return httpx.Response(200, json={"items": response_items})
            except (json.JSONDecodeError, KeyError):
                return httpx.Response(200, json={"items": []})

        rsps.post("https://example.com/api/resource").mock(side_effect=dislike_942_112_and_547)
        items = [MyReference(id=str(i)) for i in range(1000)]
        with patch("time.sleep"):
            results = client.request_with_retries(
                ItemsRequest(
                    endpoint_url="https://example.com/api/resource",
                    method="POST",
                    body=ItemIDBody(items=items),
                    max_failures_before_abort=30,
                )
            )
        failures = Counter(
            [type(message) for message in results if isinstance(message, ItemMessage) for _ in message.ids]
        )
        assert failures == {FailedResponseItems: 3, SuccessResponseItems: 997}

    def test_response_auto_retryable(self, client_config: ClientConfig, rsps: respx.MockRouter) -> None:
        with HTTPClient(client_config, max_retries=3, retry_status_codes=set()) as client:
            rsps.post("https://example.com/api/resource").respond(
                json={"error": {"message": "Server error", "code": 500, "isAutoRetryable": True}},
                status_code=500,
            )
            item = MyReference(id="1")
            with patch("time.sleep"):
                results = client.request_with_retries(
                    ItemsRequest(
                        endpoint_url="https://example.com/api/resource",
                        method="POST",
                        body=ItemIDBody(items=[item]),
                    )
                )
            assert len(results) == 1
            response = results[0]
            assert isinstance(response, FailedResponseItems)
            assert response.code == 500
            assert response.error.message == "Server error"
            assert len(rsps.calls) == 4  # Retries 3 times
