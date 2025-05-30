from abc import ABC, abstractmethod
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path
from types import UnionType
from typing import TYPE_CHECKING, Generic, TypeVar, Union, get_args, get_origin

from cognite.neat.core._client import NeatClient
from cognite.neat.core._constants import DEFAULT_NAMESPACE
from cognite.neat.core._data_model._shared import T_VerifiedDataModel
from cognite.neat.core._utils.auxiliary import class_html_doc
from cognite.neat.core._utils.upload import UploadResult, UploadResultList

if TYPE_CHECKING:
    from cognite.neat.core._store._provenance import Agent as ProvenanceAgent

T_Export = TypeVar("T_Export")


class BaseExporter(ABC, Generic[T_VerifiedDataModel, T_Export]):
    _new_line = "\n"
    _encoding = "utf-8"

    @abstractmethod
    def export_to_file(self, data_model: T_VerifiedDataModel, filepath: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def export(self, data_model: T_VerifiedDataModel) -> T_Export:
        raise NotImplementedError

    @classmethod
    def _repr_html_(cls) -> str:
        return class_html_doc(cls, include_factory_methods=False)

    @property
    def agent(self) -> "ProvenanceAgent":
        """Provenance agent for the importer."""
        from cognite.neat.core._store._provenance import Agent as ProvenanceAgent

        return ProvenanceAgent(id_=DEFAULT_NAMESPACE[f"agent/{type(self).__name__}"])

    @property
    def description(self) -> str:
        return "MISSING DESCRIPTION"

    @classmethod
    @lru_cache(maxsize=1)
    def source_types(cls) -> tuple[type, ...]:
        base_exporter = cls.__orig_bases__[0]  # type: ignore[attr-defined]
        source_type = get_args(base_exporter)[0]
        if get_origin(source_type) in [Union, UnionType]:
            return get_args(source_type)
        return (source_type,)


class CDFExporter(BaseExporter[T_VerifiedDataModel, T_Export], ABC):
    @abstractmethod
    def export_to_cdf_iterable(
        self, data_model: T_VerifiedDataModel, client: NeatClient, dry_run: bool = False
    ) -> Iterable[UploadResult]:
        raise NotImplementedError

    def export_to_cdf(
        self, data_model: T_VerifiedDataModel, client: NeatClient, dry_run: bool = False
    ) -> UploadResultList:
        return UploadResultList(self.export_to_cdf_iterable(data_model, client, dry_run))
