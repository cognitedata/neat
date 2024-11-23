from collections.abc import Set
from pathlib import Path

from cognite.client import CogniteClient
from cognite.client.data_classes import DataSet, DataSetList
from cognite.client.utils.useful_types import SequenceNotStr
from rdflib import Namespace

from ._base import DEFAULT_SKIP_METADATA_VALUES, ClassicCDFBaseExtractor, InstanceIdPrefix


class DataSetExtractor(ClassicCDFBaseExtractor[DataSet]):
    """Extract DataSets from Cognite Data Fusions into Neat."""

    _default_rdf_type = "DataSet"
    _instance_id_prefix = InstanceIdPrefix.data_set

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
