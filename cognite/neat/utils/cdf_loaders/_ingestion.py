from collections.abc import Iterable, Sequence
from itertools import groupby
from typing import cast, overload

from cognite.client.data_classes import (
    Database,
    DatabaseList,
    DatabaseWrite,
    DatabaseWriteList,
    Transformation,
    TransformationList,
    TransformationWrite,
    TransformationWriteList,
)
from cognite.client.exceptions import CogniteAPIError
from cognite.client.utils.useful_types import SequenceNotStr

from ._base import ResourceLoader
from .data_classes import RawTable, RawTableID, RawTableList, RawTableWrite, RawTableWriteList


class TransformationLoader(
    ResourceLoader[str, TransformationWrite, Transformation, TransformationWriteList, TransformationList]
):
    resource_name = "transformations"

    @classmethod
    def get_id(cls, item: Transformation | TransformationWrite) -> str:
        if item.external_id is None:
            raise ValueError(f"Transformation {item} does not have an external_id")
        return item.external_id

    def create(self, items: Sequence[TransformationWrite]) -> TransformationList:
        return self.client.transformations.create(items)

    def retrieve(self, ids: SequenceNotStr[str]) -> TransformationList:
        return self.client.transformations.retrieve_multiple(external_ids=ids, ignore_unknown_ids=True)

    def update(self, items: Sequence[TransformationWrite]) -> TransformationList:
        return self.client.transformations.update(items)

    def delete(self, ids: SequenceNotStr[str]) -> list[str]:
        existing = self.retrieve(ids)
        self.client.transformations.delete(external_id=ids, ignore_unknown_ids=True)
        return existing.as_external_ids()


class RawDatabaseLoader(ResourceLoader[str, DatabaseWrite, Database, DatabaseWriteList, DatabaseList]):
    resource_name = "databases"

    @classmethod
    def get_id(cls, item: Database | DatabaseWrite) -> str:
        if item.name is None:
            raise ValueError(f"Database {item} does not have a name")
        return item.name

    def create(self, items: Sequence[DatabaseWrite]) -> DatabaseList:
        return self.client.raw.databases.create([item.name for item in items if item.name is not None])

    def retrieve(self, ids: SequenceNotStr[str]) -> DatabaseList:
        all_databases = self.client.raw.databases.list(limit=-1)
        return DatabaseList([db for db in all_databases if db.name in ids])

    def update(self, items: Sequence[DatabaseWrite]) -> DatabaseList:
        if not items:
            return DatabaseList([])
        raise NotImplementedError("The CDF API does not support updating a RAW database.")

    def delete(self, ids: SequenceNotStr[str]) -> list[str]:
        existing_databases = self.retrieve(ids)
        existing_names = {item.name for item in existing_databases}
        self.client.raw.databases.delete([name for name in ids if name in existing_names])
        return existing_databases.as_names()


class RawTableLoader(ResourceLoader[RawTableID, RawTableWrite, RawTable, RawTableWriteList, RawTableList]):
    resource_name = "tables"

    @classmethod
    def get_id(cls, item: RawTable | RawTableWrite) -> RawTableID:
        return item.as_id()

    @overload
    def _groupby_database(self, items: Sequence[RawTableWrite]) -> Iterable[tuple[str, Iterable[RawTableWrite]]]: ...

    @overload
    def _groupby_database(self, items: SequenceNotStr[RawTableID]) -> Iterable[tuple[str, Iterable[RawTableID]]]: ...

    def _groupby_database(
        self, items: Sequence[RawTableWrite] | SequenceNotStr[RawTableID]
    ) -> Iterable[tuple[str, Iterable[RawTableWrite] | Iterable[RawTableID]]]:
        return cast(
            Iterable[tuple[str, Iterable[RawTableID] | Iterable[RawTableWrite]]],
            groupby(sorted(items, key=lambda x: x.database or ""), lambda x: x.database or ""),
        )

    def create(self, items: Sequence[RawTableWrite]) -> RawTableList:
        existing = set(self.retrieve([table.as_id() for table in items]).as_ids())
        output = RawTableList([])
        for db_name, tables in self._groupby_database(items):
            to_create = [table.name for table in tables if table.name if table.as_id() not in existing]
            if not to_create:
                continue
            created = self.client.raw.tables.create(db_name=db_name, name=to_create)
            for table in created:
                output.append(
                    RawTable(
                        name=table.name, database=db_name, created_time=table.created_time, cognite_client=self.client
                    )
                )
        return output

    def retrieve(self, ids: SequenceNotStr[RawTableID]) -> RawTableList:
        output = RawTableList([])
        for db_name, id_group in self._groupby_database(ids):
            try:
                all_tables = self.client.raw.tables.list(db_name, limit=-1)
            except CogniteAPIError as e:
                if e.code == 404 and e.message.startswith("Following databases not found"):
                    continue
            looking_for = {table_id.table for table_id in id_group if table_id.table is not None}
            output.extend(
                [
                    RawTable(
                        name=table.name, database=db_name, created_time=table.created_time, cognite_client=self.client
                    )
                    for table in all_tables
                    if table.name in looking_for
                ]
            )
        return output

    def update(self, items: Sequence[RawTableWrite]) -> RawTableList:
        if not items:
            return RawTableList([])
        raise NotImplementedError("The CDF API does not support updating a RAW table.")

    def delete(self, ids: SequenceNotStr[RawTableID]) -> list[RawTableID]:
        existing_tables = self.retrieve(ids)
        existing_names = {item.name for item in existing_tables}
        for db_name, id_group in self._groupby_database(ids):
            self.client.raw.tables.delete(
                db_name=db_name,
                name=[
                    table_id.table
                    for table_id in id_group
                    if table_id.table is not None and table_id.table in existing_names
                ],
            )
        return existing_tables.as_ids()
