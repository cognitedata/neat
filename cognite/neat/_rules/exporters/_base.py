from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path
from typing import Generic, TypeVar

from cognite.client import CogniteClient

from cognite.neat._rules._shared import T_VerifiedRules
from cognite.neat._utils.auxiliary import class_html_doc
from cognite.neat._utils.upload import UploadResult, UploadResultList

T_Export = TypeVar("T_Export")


class BaseExporter(ABC, Generic[T_VerifiedRules, T_Export]):
    _new_line = "\n"
    _encoding = "utf-8"

    @abstractmethod
    def export_to_file(self, rules: T_VerifiedRules, filepath: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def export(self, rules: T_VerifiedRules) -> T_Export:
        raise NotImplementedError

    @classmethod
    def _repr_html_(cls) -> str:
        return class_html_doc(cls, include_factory_methods=False)


class CDFExporter(BaseExporter[T_VerifiedRules, T_Export]):
    @abstractmethod
    def export_to_cdf_iterable(
        self, rules: T_VerifiedRules, client: CogniteClient, dry_run: bool = False
    ) -> Iterable[UploadResult]:
        raise NotImplementedError

    def export_to_cdf(self, rules: T_VerifiedRules, client: CogniteClient, dry_run: bool = False) -> UploadResultList:
        return UploadResultList(self.export_to_cdf_iterable(rules, client, dry_run))
