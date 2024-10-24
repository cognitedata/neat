from collections.abc import Set
from datetime import datetime, timezone
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import DataSet, DataSetList
from cognite.client.utils.useful_types import SequenceNotStr
from rdflib import RDF, Literal, Namespace

from cognite.neat._graph.models import Triple

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix


class DataSetExtractor(ClassicCDFBaseExtractor[DataSet]):
    """Extract DataSets from Cognite Data Fusions into Neat.

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

    _default_rdf_type = "DataSet"

    @classmethod
    def from_dataset(
        cls,
        client: CogniteClient,
        data_set_external_id: SequenceNotStr[str],
        namespace: Namespace | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        return cls(
            client.data_sets.retrieve_multiple(external_ids=data_set_external_id),
            namespace=namespace,
            total=len(data_set_external_id),
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    @classmethod
    def from_file(
        cls,
        file_path: str,
        namespace: Namespace | None = None,
        unpack_metadata: bool = True,
        skip_metadata_values: Set[str] | None = DEFAULT_SKIP_METADATA_VALUES,
    ):
        data_sets = DataSetList.load(Path(file_path).read_text())
        return cls(
            data_sets,
            namespace=namespace,
            total=len(data_sets),
            unpack_metadata=unpack_metadata,
            skip_metadata_values=skip_metadata_values,
        )

    def _item2triples(self, item: DataSet) -> list[Triple]:
        """Converts an asset to triples."""
        id_ = self.namespace[f"{InstanceIdPrefix.data_set}{item.id}"]

        type_ = self._get_rdf_type(item)

        triples: list[Triple] = [(id_, RDF.type, self.namespace[type_])]

        # Create attributes
        if item.name:
            triples.append((id_, self.namespace.name, Literal(item.name)))

        if item.description:
            triples.append((id_, self.namespace.description, Literal(item.description)))

        if item.external_id:
            triples.append((id_, self.namespace.external_id, Literal(item.external_id)))

        # properties' ref creation and update
        triples.append(
            (
                id_,
                self.namespace.created_time,
                Literal(datetime.fromtimestamp(item.created_time / 1000, timezone.utc)),
            )
        )
        triples.append(
            (
                id_,
                self.namespace.last_updated_time,
                Literal(datetime.fromtimestamp(item.last_updated_time / 1000, timezone.utc)),
            )
        )

        if item.write_protected:
            triples.append((id_, self.namespace.write_protected, Literal(item.write_protected)))

        if item.metadata:
            triples.extend(self._metadata_to_triples(id_, item.metadata))

        return triples
