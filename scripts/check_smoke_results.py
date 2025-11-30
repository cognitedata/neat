import sys
from pathlib import Path
import os
from datetime import date
SLACK_WEBHOOK_URL_NAME = "SLACK_WEBHOOK_URL"


def check_smoke_tests_results(pytest_report: Path, slack_webhook_url: str, today: date) -> None:
    """Check the smoke tests results from a pytest report file.

    Args:
        pytest_report (Path): Path to the pytest report file.
        slack_webhook_url (str): Slack webhook URL to send notifications.
        today (date): Today's date - this is used to determine whether to send an alive notification.
    """
    raise NotImplementedError()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python upload_smoke_results.py <results_file>")
        sys.exit(1)

    if SLACK_WEBHOOK_URL_NAME not in os.environ:
        print(f"Environment variable {SLACK_WEBHOOK_URL_NAME} is not set.")
        sys.exit(1)

    check_smoke_tests_results(Path(sys.argv[1]), os.environ[SLACK_WEBHOOK_URL_NAME], date.today())
