import sys
from collections.abc import Sequence

import pandas as pd
from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ContainerApply, MappedPropertyApply, ViewApply
from cognite.client.data_classes.data_modeling.ids import DataModelIdentifier

from ._base import BaseImporter

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class DMSImporter(BaseImporter):
    """
    Converts a Data Model Storage (DMS) data model to a set of transformation rules.

    !!! Warning
        This class is not yet implemented.
    """

    def __init__(self, containers: Sequence[ContainerApply], views: Sequence[ViewApply]):
        referenced_containers = {
            prop.container
            for view in views
            for prop in (view.properties or {}).values()
            if isinstance(prop, MappedPropertyApply)
        }
        if missing_containers := referenced_containers - {container.as_id() for container in containers}:
            raise ValueError(f"Missing containers: {missing_containers}")
        self.containers = containers
        self.views = views

    @classmethod
    def from_cdf(cls, client: CogniteClient, data_models: DataModelIdentifier | Sequence[DataModelIdentifier]) -> Self:
        raise NotImplementedError

    def to_tables(self) -> dict[str, pd.DataFrame]:
        raise NotImplementedError
