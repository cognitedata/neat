from collections.abc import Iterable
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm

from cognite.neat.graph.stores import NeatGraphStoreBase
from cognite.neat.rules.issues import NeatValidationError
from cognite.neat.rules.models import DMSRules

from ._base import CDFLoader


class DMSLoader(CDFLoader[dm.InstanceApply]):
    def __init__(
        self, data_model: dm.DataModel[dm.View], graph_store: NeatGraphStoreBase, add_class_prefix: bool = False
    ):
        self.data_model = data_model
        self.graph_store = graph_store
        self.add_class_prefix = add_class_prefix

    @classmethod
    def from_data_model_id(
        cls,
        client: CogniteClient,
        data_model_id: dm.DataModelId,
        graph_store: NeatGraphStoreBase,
        add_class_prefix: bool = False,
    ) -> "DMSLoader":
        # Todo add error handling
        data_model = client.data_modeling.data_models.retrieve(data_model_id, inline_views=True).latest_version()
        return cls(data_model, graph_store, add_class_prefix)

    @classmethod
    def from_rules(
        cls, rules: DMSRules, graph_store: NeatGraphStoreBase, add_class_prefix: bool = False
    ) -> "DMSLoader":
        schema = rules.as_schema()
        # Todo add error handling
        return cls(schema.as_read_model(), graph_store, add_class_prefix)

    def _load(self, stop_on_exception: bool = False) -> Iterable[dm.InstanceApply | NeatValidationError]:
        raise NotImplementedError()

    def write_to_file(self, filepath: Path) -> None:
        raise NotImplementedError()

    def load_into_cdf_iterable(self, client: CogniteClient, dry_run: bool = False) -> Iterable:
        raise NotImplementedError()
