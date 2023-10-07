from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from cognite.neat.rules.models import TransformationRules


class BaseImporter(ABC):
    @abstractmethod
    def to_tables(self) -> dict[str, pd.DataFrame]:
        raise NotImplementedError

    def to_spreadsheet(self, filepath: Path) -> None:
        raise NotImplementedError

    def to_rules(self) -> TransformationRules:
        raise NotImplementedError
