import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generic, TypeVar

from cognite.neat.rules.models.raw_rules import RawRules
from cognite.neat.rules.models.rules import Rules

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

T_Export = TypeVar("T_Export")


class BaseExporter(ABC, Generic[T_Export]):
    def __init__(self, rules: Rules, report: str | None = None):
        self.rules = rules
        self.report = report

    @classmethod
    def from_rules(cls, rules: RawRules | Rules) -> Self:
        if isinstance(rules, Rules):
            return cls(rules)
        elif isinstance(rules, RawRules):
            validated_rules = rules.to_rules(skip_validation=True)
            report = rules.validate_rules()
            return cls(validated_rules, report)

        raise ValueError(f"Expected RawRules or Rules, got {type(rules)}")

    def export_to_file(self, filepath: Path, report_path: Path | None = None) -> None:
        self._export_to_file(filepath)
        if self.report:
            report_path = report_path or filepath.parent / f"{filepath.stem}_validation_report.txt"
            report_path.write_text(self.report)

    @abstractmethod
    def _export_to_file(self, filepath: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def export(self) -> T_Export:
        raise NotImplementedError
