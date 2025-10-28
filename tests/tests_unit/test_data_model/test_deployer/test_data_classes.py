import pytest

from cognite.neat._data_model.deployer.data_classes import SeverityType


class TestSeverityType:
    @pytest.mark.parametrize(
        "severities,expected_max",
        [
            pytest.param(
                [SeverityType.SAFE, SeverityType.WARNING, SeverityType.BREAKING],
                SeverityType.BREAKING,
                id="max is BREAKING",
            ),
            pytest.param(
                [SeverityType.SAFE, SeverityType.WARNING],
                SeverityType.WARNING,
                id="max is WARNING",
            ),
            pytest.param(
                [SeverityType.SAFE],
                SeverityType.SAFE,
                id="max is SAFE",
            ),
            pytest.param(
                [],
                SeverityType.SAFE,
                id="empty list returns default",
            ),
        ],
    )
    def test_max_severity(self, severities: list[SeverityType], expected_max: SeverityType) -> None:
        result = SeverityType.max_severity(severities, default=SeverityType.SAFE)
        assert result == expected_max
