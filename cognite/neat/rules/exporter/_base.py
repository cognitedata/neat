from abc import ABC, abstractmethod
from pathlib import Path
from typing import cast

from cognite.neat.rules.models.raw_rules import RawRules
from cognite.neat.rules.models.rules import Rules


class BaseExporter(ABC):
    def __init__(self, rules: Rules | RawRules, filepath: Path | None = None, report_path: Path | None = None):
        self.report = None
        if rules.__class__.__name__ == RawRules.__name__:
            self.rules = cast(RawRules, rules).to_rules(skip_validation=True)
            self.report = cast(RawRules, rules).validate_rules()
        else:
            self.rules = cast(Rules, rules)
        self.filepath = filepath
        self.report_path = report_path

    @abstractmethod
    def export(self):
        raise NotImplementedError
