import sys
from collections.abc import Sequence
from datetime import datetime
from typing import cast

import pandas as pd
from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import (
    DataModel,
    DirectRelation,
    MappedProperty,
    SingleHopConnectionDefinition,
    View,
)
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

    def __init__(self, views: Sequence[View], metadata: dict[str, str | float] | None = None):
        super().__init__()
        self.views = views

        if metadata is None:
            self.metadata = self._default_metadata()
        else:
            self.metadata = metadata

    @classmethod
    def from_cdf(cls, client: CogniteClient, data_model: DataModelIdentifier) -> Self:
        """
        Converts a Data Model Storage (DMS) data model to a set of transformation rules.

        Args:
            client: Cognite client to use for fetching data models.
            data_model: List of data models to convert to transformation rules.

        !!! Note
            Beware that `DataModelIdentifier` is just type hint that you cannot instantiate
            directly, e.g. `id = DataModelIdentifier(space=, external_id, version)` will fail.
            Instead, provide `data_models` as a list of three element tuples,
            e.g. `[(space, external_id, version)]`, or two element tuples,
            e.g. `[(space, external_id)]`, where `space` represents CDF space name,
            `external_id` represents data model external ID, and `version`
            represents data model version. If `version` is not provided, the latest version
            of the data model will be used.

        """
        data_model = client.data_modeling.data_models.retrieve(data_model, inline_views=True)[0]

        # Avoid duplicate views (same view can be used by multiple data models)
        views_by_id: dict[ViewId, View] = {}
        for view in data_model.views:
            views_by_id[view.as_id()] = view

        if metadata := cls._to_metadata(data_model):
            return cls(list(views_by_id.values()), metadata)
        else:
            return cls(list(views_by_id.values()))

    def to_tables(self) -> dict[str, pd.DataFrame]:
        classes: list[dict[str, str | float]] = []
        properties: list[dict[str, str | float]] = []
        for view in self.views:
            class_id = view.external_id
            classes.append(
                {
                    "Class": class_id,
                    "Description": view.description or float("nan"),
                }
            )
            for prop_id, prop in view.properties.items():
                if isinstance(prop, MappedProperty):
                    # Edge 1-1
                    if isinstance(prop.type, DirectRelation):
                        type_ = cast(ViewId, prop.source).external_id
                    else:
                        type_ = DMS_TO_DATA_TYPE.get(type(prop.type), "string")

                # Edge 1-many
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
                        "Class": class_id,
                        "Property": prop_id,
                        "Name": prop.name if prop.name else prop_id,
                        "Description": prop.description or float("nan"),
                        "Type": type_,
                        "Min Count": "1",
                        "Max Count": max_count,
                        "Rule Type": "rdfpath",
                        "Rule": f"cim:{class_id}(cim:{prop_id}.name)",
                    }
                )

        return {
            Tables.metadata: pd.Series(self.metadata).to_frame("value").reset_index(),
            Tables.classes: pd.DataFrame(classes),
            Tables.properties: pd.DataFrame(properties),
        }

    @staticmethod
    def _to_metadata(data_mode: DataModel) -> dict:
        mapping = {
            "space": "cdf_space_name",
            "external_id": "data_model_name",
            "version": "version",
            "description": "description",
            "created_time": "created",
            "last_updated_time": "updated",
            "name": "title",
        }

        metadata = {mapping.get(k, k): v for k, v in data_mode.to_pandas().value.to_dict().items() if k in mapping}

        metadata["prefix"] = metadata["data_model_name"]
        metadata["creator"] = "Unknown"

        if "created" in metadata:
            metadata["created"] = datetime.utcfromtimestamp(metadata["created"] / 1e3)
        if "updated" in metadata:
            metadata["updated"] = datetime.utcfromtimestamp(metadata["updated"] / 1e3)

        return metadata

    def _repr_html_(self) -> str:
        """Pretty display of the DMSImporter object in a Notebook"""
        dump = self.metadata
        dump["views_count"] = len(self.views)
        return pd.Series(dump).to_frame("value")._repr_html_()  # type: ignore[operator]
