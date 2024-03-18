from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import Generic, TypeVar

from cognite.client import CogniteClient

from cognite.neat.rules._shared import Rules
from cognite.neat.rules.models._rules import DMSRules, InformationRules, RoleTypes

from ._models import UploadResult

T_Export = TypeVar("T_Export")


class BaseExporter(ABC, Generic[T_Export]):
    @abstractmethod
    def export_to_file(self, filepath: Path, rules: Rules) -> None:
        raise NotImplementedError

    @abstractmethod
    def export(self, rules: Rules) -> T_Export:
        raise NotImplementedError

    def _convert_to_output_role(self, rules: Rules, output_role: RoleTypes | None = None) -> Rules:
        if rules.metadata.role is output_role or output_role is None:
            return rules
        elif output_role is RoleTypes.dms_architect and isinstance(rules, InformationRules):
            return rules.as_dms_architect_rules()
        elif output_role is RoleTypes.information_architect and isinstance(rules, DMSRules):
            return rules.as_information_architect_rules()
        else:
            raise NotImplementedError(f"Role {output_role} is not supported for {type(rules).__name__} rules")


class CDFExporter(BaseExporter[T_Export]):
    @abstractmethod
    def export_to_cdf(self, client: CogniteClient, rules: Rules, dry_run: bool = False) -> Iterable[UploadResult]:
        raise NotImplementedError
