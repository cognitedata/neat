from collections.abc import Iterator
from pathlib import Path

import pytest
import respx
from httpx import Response

from scripts.check_smoke_results import Context, check_smoke_tests_results


@pytest.fixture
def context() -> Context:
    """Fixture to provide a dummy Context object."""
    return Context(
        slack_webhook_url="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX",
        github_repo_url="https://github.com/cognitedata/neat",
    )


@pytest.fixture
def call_slack(respx_mock: respx.MockRouter, context: Context) -> Iterator[respx.MockRouter]:
    """Fixture to mock Slack webhook calls."""
    respx_mock.post(url=context.slack_webhook_url).mock(Response(status_code=200))
    yield respx_mock


class TestCheckSmokeResults:
    def test_file_does_not_exist(self, call_slack: respx.MockRouter, context: Context) -> None:
        """Test that the function handles a non-existent file gracefully."""
        check_smoke_tests_results(Path("non_existent_file.txt"), context)

        assert len(call_slack.calls) == 1
        request = call_slack.calls[0].request
        assert "Smoke tests failed to execute" in request.content.decode()
