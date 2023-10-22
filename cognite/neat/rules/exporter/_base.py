from abc import ABC, abstractmethod
from pathlib import Path

from cognite.neat.rules.models.rules import Rules


class BaseExporter(ABC):
    def __init__(self, rules: Rules, filepath: Path | None = None, report_path: Path | None = None):
        self.rules = rules
        self.filepath = filepath
        self.report_path = report_path

    @abstractmethod
    def export(self):
        raise NotImplementedError
