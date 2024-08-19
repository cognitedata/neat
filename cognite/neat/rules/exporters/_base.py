from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import Generic, TypeVar

from cognite.client import CogniteClient

from cognite.neat.rules._shared import VerifiedRules
from cognite.neat.rules.models import DMSRules, InformationRules, RoleTypes
from cognite.neat.utils.auxiliary import class_html_doc
from cognite.neat.utils.upload import UploadResult, UploadResultList

T_Export = TypeVar("T_Export")


class BaseExporter(ABC, Generic[T_Export]):
    _new_line = "\n"
    _encoding = "utf-8"

    @abstractmethod
    def export_to_file(self, rules: VerifiedRules, filepath: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def export(self, rules: VerifiedRules) -> T_Export:
        raise NotImplementedError

    def _convert_to_output_role(self, rules: VerifiedRules, output_role: RoleTypes | None = None) -> VerifiedRules:
        if rules.metadata.role is output_role or output_role is None:
            return rules
        elif output_role is RoleTypes.dms and isinstance(rules, InformationRules):
            return rules.as_dms_rules()
        elif output_role is RoleTypes.information and isinstance(rules, DMSRules):
            return rules.as_information_rules()
        else:
            raise NotImplementedError(f"Role {output_role} is not supported for {type(rules).__name__} rules")

    @classmethod
    def _repr_html_(cls) -> str:
        return class_html_doc(cls, include_factory_methods=False)


class CDFExporter(BaseExporter[T_Export]):
    @abstractmethod
    def export_to_cdf_iterable(
        self, rules: VerifiedRules, client: CogniteClient, dry_run: bool = False
    ) -> Iterable[UploadResult]:
        raise NotImplementedError

    def export_to_cdf(self, rules: VerifiedRules, client: CogniteClient, dry_run: bool = False) -> UploadResultList:
        return UploadResultList(self.export_to_cdf_iterable(rules, client, dry_run))
