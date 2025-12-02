"""Neat sequence combines the CogniteClient sequence and the SequenceRows"""

import sys
import warnings
from abc import ABC
from collections.abc import Sequence
from typing import Any, cast

import cognite.client.data_classes as cdc
from cognite.client import CogniteClient
from cognite.client.data_classes import (
    SequenceColumn,
    SequenceColumnList,
    SequenceColumnWrite,
    SequenceColumnWriteList,
    SequenceRow,
)
from cognite.client.data_classes._base import (
    CogniteResourceList,
    ExternalIDTransformerMixin,
    IdTransformerMixin,
    WriteableCogniteResource,
    WriteableCogniteResourceList,
)

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class NeatSequenceCore(WriteableCogniteResource["NeatSequenceWrite"], ABC):
    """Information about the sequence stored in the database

    Args:
        name (str | None): Name of the sequence
        description (str | None): Description of the sequence
        asset_id (int | None): Optional asset this sequence is associated with
        external_id (str | None): The external ID provided by the client. Must be unique for the resource type.
        metadata (dict[str, Any] | None): Custom, application-specific metadata. String key -> String value.
            The maximum length of the key is 32 bytes, the value 512 bytes, with up to 16 key-value pairs.
        data_set_id (int | None): Data set that this sequence belongs to
        rows (typing.Sequence[SequenceRow] | None): The rows in the sequence.
    """

    def __init__(
        self,
        name: str | None = None,
        description: str | None = None,
        asset_id: int | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        data_set_id: int | None = None,
        rows: Sequence[SequenceRow] | None = None,
    ) -> None:
        self.name = name
        self.description = description
        self.asset_id = asset_id
        self.external_id = external_id
        self.metadata = metadata
        self.data_set_id = data_set_id
        self.rows = rows


class NeatSequenceWrite(NeatSequenceCore):
    """Information about the sequence stored in the database.
    This is the writing version of the class, it is used for inserting data into the CDF.

    Args:
        columns (typing.Sequence[SequenceColumnWrite]): List of column definitions
        name (str | None): Name of the sequence
        description (str | None): Description of the sequence
        asset_id (int | None): Optional asset this sequence is associated with
        external_id (str | None): The external ID provided by the client. Must be unique for the resource type.
        metadata (dict[str, Any] | None): Custom, application-specific metadata. String key -> String value.
            The maximum length of key is 32 bytes, value 512 bytes, up to 16 key-value pairs.
        data_set_id (int | None): Data set that this sequence belongs to
        rows (typing.Sequence[SequenceRow] | None): The rows in the sequence.
    """

    def __init__(
        self,
        columns: Sequence[SequenceColumnWrite],
        name: str | None = None,
        description: str | None = None,
        asset_id: int | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        data_set_id: int | None = None,
        rows: Sequence[SequenceRow] | None = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            asset_id=asset_id,
            external_id=external_id,
            metadata=metadata,
            data_set_id=data_set_id,
            rows=rows,
        )
        self.columns: SequenceColumnWriteList
        if isinstance(columns, SequenceColumnWriteList):
            self.columns = columns
        elif isinstance(columns, Sequence) and all(isinstance(col, SequenceColumnWrite) for col in columns):
            self.columns = SequenceColumnWriteList(columns)
        else:
            raise ValueError(f"columns must be a sequence of SequenceColumnWrite objects not {type(columns)}")

    @classmethod
    def _load(cls, resource: dict, cognite_client: CogniteClient | None = None) -> Self:
        return cls(
            columns=SequenceColumnWriteList._load(resource["columns"]),
            name=resource.get("name"),
            description=resource.get("description"),
            asset_id=resource.get("assetId"),
            external_id=resource.get("externalId"),
            metadata=resource.get("metadata"),
            data_set_id=resource.get("dataSetId"),
            rows=[SequenceRow._load(row) for row in resource.get("rows", [])],
        )

    def dump(self, camel_case: bool = True) -> dict[str, Any]:
        dumped = super().dump(camel_case)
        dumped["columns"] = self.columns.dump(camel_case)
        if self.rows is not None:
            dumped["rows"] = [row.dump(camel_case) for row in self.rows]
        return dumped

    def as_write(self) -> "NeatSequenceWrite":
        """Returns this NeatSequenceWrite."""
        return self


class NeatSequence(NeatSequenceCore):
    """Information about the sequence stored in the database.
    This is the reading version of the class, it is used for retrieving data from the CDF.

    Args:
        id (int): Unique cognite-provided identifier for the sequence
        name (str | None): Name of the sequence
        created_time (int | None): Time when this sequence was created in CDF in milliseconds since Jan 1, 1970.
        last_updated_time (int | None): The last time this sequence was updated in CDF,
            in milliseconds since Jan 1, 1970.
        description (str | None): Description of the sequence
        asset_id (int | None): Optional asset this sequence is associated with
        external_id (str | None): The external ID provided by the client. Must be unique for the resource type.
        metadata (dict[str, Any] | None): Custom, application-specific metadata. String key -> String value.
            The maximum length of the key is 32 bytes, the value 512 bytes, with up to 16 key-value pairs.
        columns (Sequence[SequenceColumn] | None): List of column definitions

        data_set_id (int | None): Data set that this sequence belongs to
        rows (Sequence[SequenceRow] | None): The rows in the sequence.
        cognite_client (CogniteClient | None): The client to associate with this object.
    """

    def __init__(
        self,
        id: int,
        created_time: int,
        last_updated_time: int,
        name: str | None = None,
        description: str | None = None,
        asset_id: int | None = None,
        external_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        columns: Sequence[SequenceColumn] | None = None,
        data_set_id: int | None = None,
        rows: Sequence[SequenceRow] | None = None,
        cognite_client: CogniteClient | None = None,
    ) -> None:
        super().__init__(
            name=name,
            description=description,
            asset_id=asset_id,
            external_id=external_id,
            metadata=metadata,
            data_set_id=data_set_id,
            rows=rows,
        )
        self.id = id
        self.created_time = created_time
        self.last_updated_time = last_updated_time

        self.columns: SequenceColumnList | None
        if columns is None or isinstance(columns, SequenceColumnList):
            self.columns = columns
        elif isinstance(columns, Sequence) and all(isinstance(col, SequenceColumn) for col in columns):
            self.columns = SequenceColumnList(columns)
        elif isinstance(columns, list):
            warnings.warn(
                "Columns is no longer a dict, you should first load the list of dictionaries using "
                "SequenceColumnList.load([{...}, {...}])",
                DeprecationWarning,
                stacklevel=2,
            )
            self.columns = SequenceColumnList._load(columns)
        else:
            raise ValueError(f"columns must be a sequence of SequenceColumn objects not {type(columns)}")
        self._cognite_client = cast("CogniteClient", cognite_client)

    @classmethod
    def from_cognite_sequence(
        cls, sequence: cdc.Sequence, rows: Sequence[cdc.SequenceRow] | None = None
    ) -> "NeatSequence":
        """Create a NeatSequence from a Cognite Sequence object."""
        args = sequence.dump(camel_case=True)
        if rows is not None:
            args["rows"] = [row.dump(camel_case=True) for row in rows]
        return cls._load(args)

    @classmethod
    def _load(cls, resource: dict, cognite_client: CogniteClient | None = None) -> Self:
        return cls(
            id=resource["id"],
            created_time=resource["createdTime"],
            last_updated_time=resource["lastUpdatedTime"],
            name=resource.get("name"),
            description=resource.get("description"),
            asset_id=resource.get("assetId"),
            external_id=resource.get("externalId"),
            metadata=resource.get("metadata"),
            columns=SequenceColumnList._load(resource["columns"]) if "columns" in resource else None,
            data_set_id=resource.get("dataSetId"),
            rows=[SequenceRow._load(row) for row in resource.get("rows", [])] or None,
        )

    def as_write(self) -> "NeatSequenceWrite":
        """Returns a writeable version of this sequence."""
        if self.columns is None:
            raise ValueError("Columns must be set for the writing version of the sequence")

        return NeatSequenceWrite(
            external_id=self.external_id,
            name=self.name,
            description=self.description,
            asset_id=self.asset_id,
            metadata=self.metadata,
            data_set_id=self.data_set_id,
            columns=self.columns.as_write(),
            rows=self.rows,
        )

    def dump(self, camel_case: bool = True) -> dict[str, Any]:
        dumped = super().dump(camel_case)
        if self.columns is not None:
            dumped["columns"] = self.columns.dump(camel_case)
        if self.rows is not None:
            dumped["rows"] = [row.dump(camel_case) for row in self.rows]
        return dumped


class NeatSequenceWriteList(CogniteResourceList[NeatSequenceWrite], ExternalIDTransformerMixin):
    _RESOURCE = NeatSequenceWrite


class NeatSequenceList(WriteableCogniteResourceList[NeatSequenceWrite, NeatSequence], IdTransformerMixin):
    _RESOURCE = NeatSequence

    def as_write(self) -> NeatSequenceWriteList:
        """Returns a writeable version of this sequence list."""
        return NeatSequenceWriteList([item.as_write() for item in self], cognite_client=self._get_cognite_client())
