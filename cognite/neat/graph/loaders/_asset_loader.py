from collections.abc import Iterable
from typing import Literal, overload

from cognite.client import CogniteClient
from cognite.client.data_classes import AssetWrite, LabelDefinitionWrite, RelationshipWrite
from pydantic_core import ErrorDetails

from cognite.neat.graph.stores import NeatGraphStoreBase
from cognite.neat.rules.models import Rules

from ._base import CogniteLoader

AssetResource = AssetWrite | RelationshipWrite | LabelDefinitionWrite


class AssetLoader(CogniteLoader[AssetResource]):
    def __init__(
        self,
        rules: Rules,
        graph_store: NeatGraphStoreBase,
        data_set_id: int,
        use_orphanage: bool = True,
        asset_external_id_prefix: str | None = None,
    ):
        super().__init__(rules, graph_store)
        self.data_set_id = data_set_id
        self.use_orphanage = use_orphanage
        self.asset_external_id_prefix = asset_external_id_prefix

    @overload
    def load(self, stop_on_exception: Literal[True]) -> Iterable[AssetResource]:
        ...

    @overload
    def load(self, stop_on_exception: Literal[False] = False) -> Iterable[AssetResource | ErrorDetails]:
        ...

    def load(self, stop_on_exception: bool = False) -> Iterable[AssetResource | ErrorDetails]:
        for _class_name, _triples in self._iterate_class_triples():
            ...
        raise NotImplementedError

    def load_to_cdf(
        self, client: CogniteClient, batch_size: int | None = 1000, max_retries: int = 1, retry_delay: int = 3
    ) -> None:
        raise NotImplementedError
