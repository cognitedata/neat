from collections.abc import Callable, Iterable, Set
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

from cognite.client import CogniteClient
from cognite.client.data_classes import Asset, AssetFilter, AssetList
from rdflib import RDF, Literal, Namespace

from cognite.neat._graph.models import Triple

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix
from ._labels import LabelsExtractor


class AssetsExtractor(ClassicCDFBaseExtractor[Asset]):
    """Extract data from Cognite Data Fusions Assets into Neat.

    Args:
        items (Iterable[Asset]): An iterable of assets.
        namespace (Namespace, optional): The namespace to use. Defaults to DEFAULT_NAMESPACE.
        to_type (Callable[[Asset], str | None], optional): A function to convert an asset to a type. Defaults to None.
            If None or if the function returns None, the asset will be set to the default type "Asset".
        total (int, optional): The total number of assets to load. If passed, you will get a progress bar if rich
            is installed. Defaults to None.
        limit (int, optional): The maximal number of assets to load. Defaults to None. This is typically used for
            testing setup of the extractor. For example, if you are extracting 100 000 assets, you might want to
            limit the extraction to 1000 assets to test the setup.
        unpack_metadata (bool, optional): Whether to unpack metadata. Defaults to False, which yields the metadata as
            a JSON string.
        skip_metadata_values (set[str] | frozenset[str] | None, optional): A set of values to skip when unpacking
            metadata. Defaults to frozenset({"nan", "null", "none", ""}).
    """

    _default_rdf_type = "Asset"

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Asset], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        total = client.assets.aggregate_count(filter=AssetFilter(data_set_ids=[{"externalId": data_set_external_id}]))

        return cls(
            client.assets(data_set_external_ids=data_set_external_id),
            namespace,
            to_type,
            total,
            limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    @classmethod
    def from_hierarchy(
        cls,
        client: CogniteClient,
        root_asset_external_id: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Asset], str | None] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        total = client.assets.aggregate_count(
            filter=AssetFilter(asset_subtree_ids=[{"externalId": root_asset_external_id}])
        )

        return cls(
            cast(
                Iterable[Asset],
                client.assets(asset_subtree_external_ids=root_asset_external_id),
            ),
            namespace,
            to_type,
            total,
            limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str,
        namespace: Namespace | None = None,
        to_type: Callable[[Asset], str] | None = None,
        limit: int | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        assets = AssetList.load(Path(file_path).read_text())
        return cls(
            assets,
            namespace,
            to_type,
            total=len(assets),
            limit=limit,
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    def _item2triples(self, asset: Asset) -> list[Triple]:
        """Converts an asset to triples."""
        id_ = self.namespace[f"{InstanceIdPrefix.asset}{asset.id}"]

        type_ = self._get_rdf_type(asset)

        triples: list[Triple] = [(id_, RDF.type, self.namespace[type_])]

        # Create attributes
        if asset.name:
            triples.append((id_, self.namespace.name, Literal(asset.name)))

        if asset.description:
            triples.append((id_, self.namespace.description, Literal(asset.description)))

        if asset.external_id:
            triples.append((id_, self.namespace.external_id, Literal(asset.external_id)))

        if asset.source:
            triples.append((id_, self.namespace.source, Literal(asset.source)))

        # properties' ref creation and update
        triples.append(
            (
                id_,
                self.namespace.created_time,
                Literal(datetime.fromtimestamp(asset.created_time / 1000, timezone.utc)),
            )
        )
        triples.append(
            (
                id_,
                self.namespace.last_updated_time,
                Literal(datetime.fromtimestamp(asset.last_updated_time / 1000, timezone.utc)),
            )
        )

        if asset.labels:
            for label in asset.labels:
                # external_id can create ill-formed URIs, so we create websafe URIs
                # since labels do not have internal ids, we use the external_id as the id
                triples.append(
                    (
                        id_,
                        self.namespace.label,
                        self.namespace[f"{InstanceIdPrefix.label}{LabelsExtractor._label_id(label)}"],
                    )
                )

        if asset.metadata:
            triples.extend(self._metadata_to_triples(id_, asset.metadata))

        # Create connections:
        if asset.parent_id:
            triples.append((id_, self.namespace.parent, self.namespace[f"{InstanceIdPrefix.asset}{asset.parent_id}"]))

        if asset.root_id:
            triples.append((id_, self.namespace.root, self.namespace[f"{InstanceIdPrefix.asset}{asset.root_id}"]))

        if asset.data_set_id:
            triples.append(
                (
                    id_,
                    self.namespace.dataset,
                    self.namespace[f"{InstanceIdPrefix.data_set}{asset.data_set_id}"],
                )
            )

        return triples
