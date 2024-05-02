import sys
from collections.abc import Sequence
from datetime import datetime
from typing import Any, cast

import pandas as pd
from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import (
    DataModel,
    DirectRelation,
    EdgeConnection,
    MappedProperty,
    SingleHopConnectionDefinition,
    View,
)
from cognite.client.data_classes.data_modeling.ids import DataModelIdentifier, ViewId

from cognite.neat.legacy.rules.models.tables import Tables
from cognite.neat.legacy.rules.models.value_types import DMS_VALUE_TYPE_MAPPINGS, XSD_VALUE_TYPE_MAPPINGS

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

    def __init__(self, views: Sequence[View] | DataModel[View], metadata: dict[str, str | float] | None = None):
        if isinstance(views, DataModel):
            self.views = views.views
        else:
            self.views = list(views)

        if metadata is None:
            self.metadata = self._default_metadata()
            if len(self.views) == 1:
                self.metadata["version"] = self.views[0].version
                self.metadata["prefix"] = self.views[0].space
        else:
            self.metadata = metadata

        if isinstance(views, DataModel):
            if views.name:
                self.metadata["title"] = views.name
            if views.description:
                self.metadata["description"] = views.description
            if views.space:
                self.metadata["prefix"] = views.space
            if views.external_id:
                self.metadata["suffix"] = views.external_id
            if views.version:
                self.metadata["version"] = views.version

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
            represents data model version. If `version` is not provided, whatever is
            the first version CDF returns it will give you that one.

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
                    "Name": view.name or float("nan"),
                    "Description": view.description or float("nan"),
                }
            )
            for prop_id, prop in view.properties.items():
                if isinstance(prop, MappedProperty):
                    # Edge 1-1
                    if isinstance(prop.type, DirectRelation):
                        type_ = cast(ViewId, prop.source).external_id
                    else:
                        type_ = cast(
                            str, DMS_VALUE_TYPE_MAPPINGS.get(type(prop.type), XSD_VALUE_TYPE_MAPPINGS["string"]).xsd
                        )

                    default_value = prop.default_value
                    name = prop.name or prop_id
                    description = prop.description or float("nan")

                # Edge 1-many
                elif isinstance(prop, EdgeConnection):
                    type_ = prop.source.external_id
                    default_value = None
                    name = prop.name or prop_id
                    description = prop.description or float("nan")
                else:
                    raise NotImplementedError(f"Property type {type(prop)} not supported")

                max_count: str | float = "1"
                if isinstance(prop, SingleHopConnectionDefinition) or (
                    isinstance(prop, MappedProperty) and prop.type.is_list
                ):
                    max_count = float("nan")

                min_count: str | float = "1"
                if isinstance(prop, SingleHopConnectionDefinition) or (
                    isinstance(prop, MappedProperty) and prop.nullable
                ):
                    min_count = "0"

                properties.append(
                    {
                        "Class": class_id,
                        "Property": prop_id,
                        "Name": name,
                        "Description": description,
                        "Type": type_,
                        "Default": cast(Any, default_value),  # fixes issues with mypy
                        "Min Count": min_count,
                        "Max Count": max_count,
                        "Rule Type": "rdfpath",
                        "Rule": f"cim:{class_id}(cim:{prop_id})",
                    }
                )

        return {
            Tables.metadata: pd.Series(self.metadata).to_frame("value").reset_index(),
            Tables.classes: pd.DataFrame(classes),
            Tables.properties: pd.DataFrame(properties),
        }

    @staticmethod
    def _to_metadata(data_model: DataModel) -> dict:
        mapping = {
            "space": "cdf_space_name",
            "external_id": "data_model_name",
            "version": "version",
            "description": "description",
            "created_time": "created",
            "last_updated_time": "updated",
            "name": "title",
        }

        metadata = {mapping.get(k, k): v for k, v in data_model.to_pandas().value.to_dict().items() if k in mapping}

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
