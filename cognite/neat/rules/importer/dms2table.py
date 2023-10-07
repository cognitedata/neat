import sys
from collections.abc import Sequence

import pandas as pd
from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ContainerApply, NodeApply
from cognite.client.data_classes.data_modeling.ids import DataModelIdentifier

from ._base import BaseImporter

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class InformationModelImporter(BaseImporter):
    def __init__(self, containers: Sequence[ContainerApply], node_types: Sequence[NodeApply]):
        self.containers = containers
        self.node_types = node_types

    @classmethod
    def from_cdf(cls, client: CogniteClient, data_models: DataModelIdentifier | Sequence[DataModelIdentifier]) -> Self:
        raise NotImplementedError

    def to_tables(self) -> dict[str, pd.DataFrame]:
        raise NotImplementedError
