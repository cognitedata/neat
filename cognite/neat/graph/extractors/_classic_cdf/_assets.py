from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from cognite.client import CogniteClient
from cognite.client.data_classes import Asset, AssetList
from rdflib import RDF, Literal, Namespace

from cognite.neat.constants import DEFAULT_NAMESPACE
from cognite.neat.graph.extractors._base import BaseExtractor
from cognite.neat.graph.models import Triple
from cognite.neat.utils.utils import create_sha256_hash, string_to_ideal_type


class AssetsExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusions Assets into Neat.

    Args:
        assets (Iterable[Asset]): An iterable of assets.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        to_type (Callable[[Asset], str | None], optional): A function to convert an asset to a type. Defaults to None.
            If None or if the function returns None, the asset will be set to the default type "Asset".
    """

    def __init__(
        self,
        assets: Iterable[Asset],
        namespace: Namespace | None = None,
        to_type: Callable[[Asset], str | None] | None = None,
    ):
        self.namespace = namespace or DEFAULT_NAMESPACE
        self.assets = assets
        self.to_type = to_type

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Asset], str | None] | None = None,
    ):
        return cls(cast(Iterable[Asset], client.assets(data_set_external_ids=data_set_external_id)), namespace, to_type)

    @classmethod
    def from_hierarchy(
        cls,
        client: CogniteClient,
        root_asset_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Asset], str | None] | None = None,
    ):
        return cls(
            cast(Iterable[Asset], client.assets(asset_subtree_external_ids=root_asset_external_id)), namespace, to_type
        )

    @classmethod
    def from_file(
        cls, file_path: str, namespace: Namespace | None = None, to_type: Callable[[Asset], str] | None = None
    ):
        return cls(AssetList.load(Path(file_path).read_text()), namespace, to_type)

    def extract(self) -> Iterable[Triple]:
        """Extracts an asset with the given asset_id."""
        for asset in self.assets:
            yield from self._asset2triples(asset, self.namespace)

    def _asset2triples(self, asset: Asset, namespace: Namespace) -> list[Triple]:
        """Converts an asset to triples."""
        id_ = namespace[f"Asset_{asset.id}"]

        # Set rdf type
        type_ = "Asset"
        if self.to_type:
            type_ = self.to_type(asset) or type_
        triples: list[Triple] = [(id_, RDF.type, namespace[type_])]

        # Create attributes
        if asset.name:
            triples.append((id_, namespace.name, Literal(asset.name)))

        if asset.description:
            triples.append((id_, namespace.description, Literal(asset.description)))

        if asset.external_id:
            triples.append((id_, namespace.external_id, Literal(asset.external_id)))

        if asset.source:
            triples.append((id_, namespace.source, Literal(asset.source)))

        # properties ref creation and update
        triples.append(
            (
                id_,
                namespace.created_time,
                Literal(datetime.fromtimestamp(asset.created_time / 1000, timezone.utc)),
            )
        )
        triples.append(
            (
                id_,
                namespace.last_updated_time,
                Literal(datetime.fromtimestamp(asset.last_updated_time / 1000, timezone.utc)),
            )
        )

        if asset.labels:
            for label in asset.labels:
                # external_id can create ill-formed URIs, so we create websafe URIs
                # since labels do not have internal ids, we use the external_id as the id
                triples.append(
                    (id_, namespace.label, namespace[f"Label_{create_sha256_hash(label.dump()['externalId'])}"])
                )

        if asset.metadata:
            for key, value in asset.metadata.items():
                if value:
                    triples.append((id_, namespace[key], Literal(string_to_ideal_type(value))))

        # Create connections:
        if asset.parent_id:
            triples.append((id_, namespace.parent, namespace[f"Asset_{asset.parent_id}"]))

        if asset.root_id:
            triples.append((id_, namespace.root, namespace[f"Asset_{asset.root_id}"]))

        if asset.data_set_id:
            triples.append((id_, namespace.dataset, namespace[f"Dataset_{asset.data_set_id}"]))

        return triples
