import sys
from collections.abc import Sequence

import pandas as pd
from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import MappedProperty, SingleHopConnectionDefinition, View
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType
from cognite.client.data_classes.data_modeling.ids import DataModelIdentifier, ViewId

from cognite.neat.rules.models.tables import Tables
from cognite.neat.rules.type_mapping import DMS_TO_DATA_TYPE

from ._base import BaseImporter

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class DMSImporter(BaseImporter):
    """
    Converts a Data Model Storage (DMS) data model to a set of transformation rules.

    Args:
        views: List of views to convert to transformation rules.
    """

    def __init__(self, views: Sequence[View]):
        super().__init__()
        self.views = views

    @classmethod
    def from_cdf(cls, client: CogniteClient, data_models: DataModelIdentifier | Sequence[DataModelIdentifier]) -> Self:
        """
        Converts a Data Model Storage (DMS) data model to a set of transformation rules.

        Args:
            client: Cognite client to use for fetching data models.
            data_models: List of data models to convert to transformation rules.
        """
        data_models = client.data_modeling.data_models.retrieve(data_models, inline_views=True)

        # Avoid duplicate views (same view can be used by multiple data models)
        views_by_id: dict[ViewId, View] = {}
        for data_model in data_models:
            for view in data_model.views:
                views_by_id[view.as_id()] = view

        return cls(list(views_by_id.values()))

    def to_tables(self) -> dict[str, pd.DataFrame]:
        classes: list[dict[str, str | float]] = []
        properties: list[dict[str, str | float]] = []
        for view in self.views:
            class_name = view.external_id
            classes.append(
                {
                    "Class": class_name,
                    "Description": view.description or float("nan"),
                    "Resource Type": "Asset",
                    "Parent Asset": "Missing",
                }
            )
            for prop_name, prop in view.properties.items():
                if isinstance(prop, MappedProperty):
                    type_ = DMS_TO_DATA_TYPE.get(type(prop.type), "string")
                elif isinstance(prop, SingleHopConnectionDefinition):
                    type_ = prop.source.external_id
                else:
                    raise NotImplementedError(f"Property type {type(prop)} not supported")

                max_count: str | float = "1"
                if isinstance(prop, SingleHopConnectionDefinition) or (
                    isinstance(prop, MappedProperty)
                    and isinstance(prop.type, ListablePropertyType)
                    and prop.type.is_list
                ):
                    max_count = float("nan")

                properties.append(
                    {
                        "Class": class_name,
                        "Property": prop_name,
                        "Description": prop.description or float("nan"),
                        "Type": type_,
                        "Min Count": "1",
                        "Max Count": max_count,
                        "Resource Type": "Asset",
                        "Resource Type Property": "name",
                        "Relationship Label": float("nan"),
                        "Rule Type": "rdfpath",
                        "Rule": f"cim:{class_name}(cim:{prop_name}.name)",
                    }
                )
        metadata = self._default_metadata()

        return {
            Tables.metadata: pd.Series(metadata).to_frame("value").reset_index(),
            Tables.classes: pd.DataFrame(classes),
            Tables.properties: pd.DataFrame(properties),
        }
