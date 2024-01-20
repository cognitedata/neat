from collections.abc import Iterable
from typing import Literal, overload

from cognite.client import CogniteClient
from cognite.client.data_classes import AssetWrite, LabelDefinitionWrite, RelationshipWrite
from pydantic_core import ErrorDetails

from ._base import CogniteLoader

AssetResource = AssetWrite | RelationshipWrite | LabelDefinitionWrite


class AssetLoader(CogniteLoader[AssetResource]):
    @overload
    def load(self, stop_on_exception: Literal[True]) -> Iterable[AssetResource]:
        ...

    @overload
    def load(self, stop_on_exception: Literal[False] = False) -> Iterable[AssetResource | ErrorDetails]:
        ...

    def load(self, stop_on_exception: bool = False) -> Iterable[AssetResource | ErrorDetails]:
        raise NotImplementedError

    def load_to_cdf(
        self, client: CogniteClient, batch_size: int | None = 1000, max_retries: int = 1, retry_delay: int = 3
    ) -> None:
        raise NotImplementedError
