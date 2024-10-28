from logging import getLogger

from cognite.neat._issues import NeatError, NeatIssue, NeatWarning

from .base import Tracker


class LogTracker(Tracker):
    def __init__(self, name: str, units: list[str], unit_type: str) -> None:
        super().__init__(name, units, unit_type)
        self._logger = getLogger(__name__)
        self._total_units = len(units)
        self._count = 1
        self._logger.info(f"Staring {self.name} and will process {len(units)} {unit_type}.")

    def start(self, unit: str) -> None:
        self._logger.info(f"Starting {unit} {self._count}/{self._total_units}.")
        self._count += 1

    def finish(self, unit: str) -> None:
        self._logger.info(f"Finished {unit}.")

    def _issue(self, issue: NeatIssue) -> None:
        if isinstance(issue, NeatWarning):
            self._logger.warning(issue)
        elif isinstance(issue, NeatError):
            self._logger.error(issue)
