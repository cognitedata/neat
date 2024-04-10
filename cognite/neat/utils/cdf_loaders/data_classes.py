from abc import ABC
from dataclasses import dataclass
from typing import Any, cast

from cognite.client import CogniteClient
from cognite.client.data_classes._base import (
    CogniteResourceList,
    WriteableCogniteResource,
    WriteableCogniteResourceList,
)

# The Table, TableWrite data classes in the Cognite-SDK lacks the database attribute.
# This is a problem when creating the RawTableLoader that needs the data class to be able to create, update, retrieve
# and delete tables.
# This is a reimplemented version of the Table, TableWrite data classes with the database attribute added.


@dataclass(frozen=True)
class RawTableID:
    table: str
    database: str

    def as_tuple(self) -> tuple[str, str]:
        return self.database, self.table


class RawTableCore(WriteableCogniteResource["RawTableWrite"], ABC):
    """A NoSQL database table to store customer data

    Args:
        name (str | None): Unique name of the table
    """

    def __init__(
        self,
        name: str | None = None,
        database: str | None = None,
    ) -> None:
        self.name = name
        self.database = database

    def as_id(self) -> RawTableID:
        if self.name is None or self.database is None:
            raise ValueError("name and database are required to create a TableID")
        return RawTableID(table=self.name, database=self.database)


class RawTable(RawTableCore):
    """A NoSQL database table to store customer data.
    This is the reading version of the Table class, which is used when retrieving a table.

    Args:
        name (str | None): Unique name of the table
        created_time (int | None): Time the table was created.
        cognite_client (CogniteClient | None): The client to associate with this object.
    """

    def __init__(
        self,
        name: str | None = None,
        database: str | None = None,
        created_time: int | None = None,
        cognite_client: CogniteClient | None = None,
    ) -> None:
        super().__init__(name, database)
        self.created_time = created_time
        self._cognite_client = cast("CogniteClient", cognite_client)

        self._db_name: str | None = None

    def as_write(self) -> "RawTableWrite":
        """Returns this Table as a TableWrite"""
        if self.name is None or self.database is None:
            raise ValueError("name and database are required to create a Table")
        return RawTableWrite(name=self.name, database=self.database)


class RawTableWrite(RawTableCore):
    """A NoSQL database table to store customer data
    This is the writing version of the Table class, which is used when creating a table.

    Args:
        name (str): Unique name of the table
    """

    def __init__(
        self,
        name: str,
        database: str,
    ) -> None:
        super().__init__(name, database)

    @classmethod
    def _load(cls, resource: dict[str, Any], cognite_client: CogniteClient | None = None) -> "RawTableWrite":
        return cls(resource["name"], resource["database"])

    def as_write(self) -> "RawTableWrite":
        """Returns this TableWrite instance."""
        return self


class RawTableWriteList(CogniteResourceList[RawTableWrite]):
    _RESOURCE = RawTableWrite

    def as_ids(self) -> list[RawTableID]:
        """Returns this TableWriteList as a list of TableIDs"""
        return [table.as_id() for table in self.data]


class RawTableList(
    WriteableCogniteResourceList[RawTableWrite, RawTable],
):
    _RESOURCE = RawTable

    def as_write(self) -> RawTableWriteList:
        """Returns this TableList as a TableWriteList"""
        return RawTableWriteList([table.as_write() for table in self.data])

    def as_ids(self) -> list[RawTableID]:
        """Returns this TableList as a list of TableIDs"""
        return [table.as_id() for table in self.data]
