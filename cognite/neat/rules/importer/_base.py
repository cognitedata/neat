from abc import ABC, abstractmethod
from pathlib import Path

from cognite.neat.rules.models import TransformationRules
from cognite.neat.rules.parser import RawTables


class BaseImporter(ABC):
    @abstractmethod
    def to_tables(self) -> RawTables:
        raise NotImplementedError

    def to_spreadsheet(self, filepath: Path) -> None:
        raise NotImplementedError

    def to_rules(self) -> TransformationRules:
        raise NotImplementedError
