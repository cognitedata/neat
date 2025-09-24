import sys
from datetime import datetime

if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    from datetime import timezone

    UTC = timezone.utc


def epoch_now_ms() -> int:
    return int((datetime.now(UTC) - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds() * 1000)


def datetime_utc_now() -> datetime:
    return datetime.now(UTC)
