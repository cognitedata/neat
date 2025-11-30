import sys
from pathlib import Path
import os
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Literal, TypeAlias
import httpx
from pydantic import BaseModel, JsonValue
# Environment variable names
SLACK_WEBHOOK_URL_NAME = "SLACK_WEBHOOK_URL"
GITHUB_REPO_URL_NAME = "GITHUB_REPO_URL"

@dataclass
class Context:
    slack_webhook_url: str
    github_repo_url: str
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class SlackMessage(BaseModel):
    topic: Literal["Smoke Test Execution", "DMS Service", "Cognite Core Model"]
    message: str


def check_smoke_tests_results(pytest_report: Path, context: Context) -> None:
    """Check the smoke tests results from a pytest report file.

    Args:
        pytest_report (Path): Path to the pytest report file.
        context (Context): Context object that contains information about the test run.
    """
    report = _load_pytest_report(pytest_report, context)
    if report is None:
        return None

    messages = _check_results(report, context)

    if not messages:
        if alive_message := _alive_message(context.now):
            _notify_slack([alive_message], context)
        return None

    _notify_slack(messages, context)
    return None


Outcome: TypeAlias = Literal["passed", "failed", "skipped", "error", "xfailed", "xpassed"]

class Summary(BaseModel):
    collected: int
    total: int
    deselected: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0

class CrashInfo(BaseModel):
    path: Path
    lineno: int
    message: str

class TestStage(BaseModel):
    duration: float
    outcome: Outcome
    crash: CrashInfo | None = None
    traceback: list[JsonValue] | None = None
    stdout: str | None = None
    stderr: str | None = None
    log: list[JsonValue] | None = None
    longrepr: JsonValue | None = None


class TestResult(BaseModel):
    nodeid: str
    lineno: int
    outcome: Literal["passed", "failed", "skipped", "error", "xfailed", "xpassed"]
    setup: TestStage | None = None
    call: TestStage | None = None
    teardown: TestStage | None = None
    keywords: list[str] | None = None
    metadata: JsonValue | None = None

class PytestReportModel(BaseModel):
    created: float
    duration: float
    exitcode: int
    root: Path
    environment: dict[str, JsonValue]
    summary: Summary
    collectors: list[JsonValue] | None = None
    tests: list[TestResult] | None = None
    warnings: list[JsonValue] | None = None

def _load_pytest_report(pytest_report: Path, context: Context) -> PytestReportModel | None:
    if not pytest_report.is_file():
        _notify_slack([SlackMessage(
            topic="Smoke Test Execution",
            message=f"Smoke tests failed to execute. Report file {pytest_report.name!r} does not exist. Go to {context.github_repo_url} to investigate."
        )], context)
        return None
    try:
        return PytestReportModel.model_validate_json(pytest_report.read_text())
    except ValueError as _:
        _notify_slack([SlackMessage(
            topic="Smoke Test Execution",
            message=f"Smoke tests failed to execute. Report file {pytest_report.name!r} is not a valid pytest report. Go to {context.github_repo_url} to investigate."
        )], context)
        return None


def _check_results(report: PytestReportModel, context: Context) -> list[SlackMessage]:
    raise NotImplementedError()

def _alive_message(now: datetime) -> SlackMessage | None:
    """Create an "alive" message if the current time is Monday in the morning UTC."""
    if now.weekday() == 0 and 2 <= now.hour < 10:
        return SlackMessage(
            topic="Smoke Test Execution",
            message="Smoke tests are running fine. No issues detected. Have a great week ahead!"
        )
    return None


def _notify_slack(messages: list[SlackMessage], context: Context) -> None:
    for message in messages:
        httpx.post(context.slack_webhook_url, content=message.model_dump_json())


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python upload_smoke_results.py <results_file>")
        sys.exit(1)

    if SLACK_WEBHOOK_URL_NAME not in os.environ:
        print(f"Environment variable {SLACK_WEBHOOK_URL_NAME} is not set.")
        sys.exit(1)
    if GITHUB_REPO_URL_NAME not in os.environ:
        print(f"Environment variable {GITHUB_REPO_URL_NAME} is not set.")
        sys.exit(1)

    check_smoke_tests_results(Path(sys.argv[1]), Context(
        slack_webhook_url=os.environ[SLACK_WEBHOOK_URL_NAME],
        github_repo_url=os.environ[GITHUB_REPO_URL_NAME],
    ))
