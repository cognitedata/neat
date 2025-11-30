import sys
from pathlib import Path
import os
from datetime import datetime, timezone
from dataclasses import dataclass, field

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
