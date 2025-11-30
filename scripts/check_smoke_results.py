import sys
from pathlib import Path
import os
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from pydantic import BaseModel, JsonValue
# Environment variable names
SLACK_WEBHOOK_URL_NAME = "SLACK_WEBHOOK_URL"
GITHUB_REPO_URL_NAME = "GITHUB_REPO_URL"

@dataclass
class Context:
    slack_webhook_url: str
    github_repo_url: str
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


def check_smoke_tests_results(pytest_report: Path, context: Context) -> None:
    """Check the smoke tests results from a pytest report file.

    Args:
        pytest_report (Path): Path to the pytest report file.
        context (Context): Context object that contains information about the test run.
    """
    raise NotImplementedError()


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
