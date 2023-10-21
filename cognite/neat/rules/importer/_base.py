from abc import ABC, abstractmethod

import pandas as pd
from pydantic_core import ErrorDetails

from cognite.neat.rules.models.raw_rules import RawRules
from cognite.neat.rules.models.rules import Rules


class BaseImporter(ABC):
    @abstractmethod
    def __init__(self):
        ...

    @abstractmethod
    def to_tables(self) -> dict[str, pd.DataFrame]:
        raise NotImplementedError

    def to_raw_rules(self) -> RawRules:
        tables = self.to_tables()

        return RawRules.from_tables(tables=tables, importer_type=self.__class__.__name__)

    def to_rules(
        self, return_report: bool = False, skip_validation: bool = False
    ) -> tuple[Rules | None, list[ErrorDetails] | None, list | None] | Rules:
        raw_rules = self.to_raw_rules()
        return raw_rules.to_rules(return_report, skip_validation)
