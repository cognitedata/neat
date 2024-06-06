from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import cast

import pytz
from cognite.client import CogniteClient
from cognite.client.data_classes import Asset, AssetList
from rdflib import RDF, Literal, Namespace

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.utils import string_to_ideal_type


class AssetsExtractor(BaseExtractor):
    def __init__(
        self,
        assets: Iterable[Asset],
        namespace: Namespace | None = None,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.assets = assets

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
    ):
        return cls(cast(Iterable[Asset], client.assets(data_set_external_ids=data_set_external_id)), namespace)

    @classmethod
    def from_hierarchy(cls, client: CogniteClient, root_asset_external_id: str, namespace: Namespace | None = None):
        return cls(cast(Iterable[Asset], client.assets(asset_subtree_external_ids=root_asset_external_id)), namespace)

    @classmethod
    def from_file(cls, file_path: str, namespace: Namespace | None = None):
        return cls(AssetList.load(Path(file_path).read_text()), namespace)

    def extract(self) -> Iterable[Triple]:
        """Extracts an asset with the given asset_id."""
        for asset in self.assets:
            yield from self._asset2triples(asset, self.namespace)

    @classmethod
    def _asset2triples(cls, asset: Asset, namespace: Namespace) -> list[Triple]:
        """Converts an asset to triples."""

        # Set rdf type
        triples: list[Triple] = [(namespace[str(asset.id)], RDF.type, namespace["Asset"])]

        # Create attributes
        if asset.name:
            triples.append((namespace[str(asset.id)], namespace["name"], Literal(asset.name)))

        if asset.description:
            triples.append((namespace[str(asset.id)], namespace["description"], Literal(asset.description)))

        if asset.external_id:
            triples.append((namespace[str(asset.id)], namespace["external_id"], Literal(asset.external_id)))

        if asset.source:
            triples.append((namespace[str(asset.id)], namespace["source"], Literal(asset.source)))

        # properties ref creation and update
        triples.append(
            (
                namespace[str(asset.id)],
                namespace["created_time"],
                Literal(datetime.fromtimestamp(asset.created_time / 1000, pytz.utc)),
            )
        )
        triples.append(
            (
                namespace[str(asset.id)],
                namespace["last_updated_time"],
                Literal(datetime.fromtimestamp(asset.last_updated_time / 1000, pytz.utc)),
            )
        )

        if asset.labels:
            for label in asset.labels:
                # external_id can create ill-formed URIs, so we opt for Literal instead
                triples.append((namespace[str(asset.id)], namespace["label"], Literal(label.dump()["externalId"])))

        if asset.metadata:
            for key, value in asset.metadata.items():
                if value:
                    triples.append((namespace[str(asset.id)], namespace[key], Literal(string_to_ideal_type(value))))

        # Create connections:
        if asset.parent_id:
            triples.append((namespace[str(asset.id)], namespace["parent"], namespace[str(asset.parent_id)]))

        if asset.root_id:
            triples.append((namespace[str(asset.id)], namespace["root"], namespace[str(asset.root_id)]))

        if asset.data_set_id:
            triples.append((namespace[str(asset.id)], namespace["dataset"], namespace[str(asset.data_set_id)]))

        return triples
