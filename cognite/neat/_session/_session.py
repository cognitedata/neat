from cognite.client import ClientConfig, CogniteClient

from cognite.neat._client import NeatClient
from cognite.neat._store import NeatStore

from ._physical import PhysicalDataModel


class NeatSession:
    """A session is an interface for neat operations. It works as
    a manager for handling user interactions and orchestrating
    the state machine for data model and instance operations.
    """

    def __init__(self, client: CogniteClient | ClientConfig) -> None:
        self._store = NeatStore()
        self._client = NeatClient(client)
        self.physical_data_model = PhysicalDataModel(self._store, self._client)
        self.issues = Issues(self._store)


class Issues:
    """Class to handle issues in the NeatSession."""

    def __init__(self, store: NeatStore) -> None:
        self._store = store

    def __call__(self) -> None:
        if change := self._store.provenance.last_change:
            if change.errors:
                print("Critical Issues")
                for type_, issues in change.errors.by_type().items():
                    print(f"{type_.__name__}:")
                    for issue in issues:
                        print(f"- {issue.message}")

            if change.issues:
                print("Non-Critical Issues")
                for type_, issues in change.issues.by_type().items():
                    print(f"{type_.__name__}:")
                    for issue in issues:
                        print(f"- {issue.message}")
