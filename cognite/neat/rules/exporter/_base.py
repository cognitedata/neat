from abc import ABC, abstractmethod
from pathlib import Path
from typing import cast

from cognite.neat.rules.models.rules import Rules


class BaseExporter(ABC):
    def __init__(self, rules: Rules, filepath: Path | None = None, report_path: Path | None = None):
        self.rules = rules
        self.filepath = filepath
        self.report_path = report_path

        if filepath and not report_path:
            self.report_path = cast(Path, self.filepath).parent / "report.txt"

    @abstractmethod
    def export(self):
        raise NotImplementedError
