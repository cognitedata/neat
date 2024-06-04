from datetime import datetime

import pytz
from cognite.client import CogniteClient
from cognite.client.data_classes import Asset
from rdflib import RDF, Literal, Namespace

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.models import Triple
from cognite.neat.utils.utils import string_to_ideal_type

from ._base import BaseExtractor


class AssetExtractor(BaseExtractor):
    def __init__(self, client: CogniteClient, data_set_id: int | None = None, namespace: Namespace | None = None):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.client = client
        self.dataset_id = data_set_id

    def extract(self, limit: int = -1) -> list[Triple]:
        """Extracts an asset with the given asset_id."""

        triples: list[Triple] = []
        for asset in self.client.assets.list(limit=limit, data_set_ids=self.dataset_id):
            triples.extend(self._asset2triples(asset, self.namespace))

        return triples

    @classmethod
    def _asset2triples(cls, asset: Asset, namespace: Namespace) -> list[Triple]:
        """Converts an asset to triples."""
        triples: list[Triple] = []

        triples.append((namespace[str(asset.id)], RDF.type, namespace["Asset"]))

        if asset.name:
            triples.append((namespace[str(asset.id)], namespace["name"], Literal(asset.name)))

        if asset.description:
            triples.append((namespace[str(asset.id)], namespace["description"], Literal(asset.description)))

        if asset.external_id:
            triples.append((namespace[str(asset.id)], namespace["externalId"], Literal(asset.external_id)))

        if asset.source:
            triples.append((namespace[str(asset.id)], namespace["source"], Literal(asset.source)))

        # properties ref creation and update
        triples.append(
            (
                namespace[str(asset.id)],
                namespace["createdTime"],
                Literal(datetime.fromtimestamp(asset.created_time / 1000, pytz.utc)),
            )
        )
        triples.append(
            (
                namespace[str(asset.id)],
                namespace["lastUpdatedTime"],
                Literal(datetime.fromtimestamp(asset.last_updated_time / 1000, pytz.utc)),
            )
        )

        if asset.parent_id:
            triples.append((namespace[str(asset.id)], namespace["parent"], namespace[str(asset.parent_id)]))

        if asset.root_id:
            triples.append((namespace[str(asset.id)], namespace["root"], namespace[str(asset.root_id)]))

        if asset.data_set_id:
            triples.append((namespace[str(asset.id)], namespace["dataset"], namespace[str(asset.data_set_id)]))

        if asset.labels:
            for label in asset.labels:
                triples.append((namespace[str(asset.id)], namespace["label"], namespace[label.dump()["externalId"]]))

        if asset.metadata:
            for key, value in asset.metadata.items():
                if value:
                    triples.append((namespace[str(asset.id)], namespace[key], Literal(string_to_ideal_type(value))))

        return triples
