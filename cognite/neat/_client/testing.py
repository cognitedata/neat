from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from cognite.client.testing import CogniteClientMock

from cognite.neat._client._api_client import NeatClient

from ._api.data_modeling_loaders import DataModelLoaderAPI
from ._api.schema import SchemaAPI


class NeatClientMock(CogniteClientMock):
    """Mock for ToolkitClient object

    All APIs are replaced with specked MagicMock objects.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if "parent" in kwargs:
            super().__init__(*args, **kwargs)
            return
        super().__init__(*args, **kwargs)
        self.schema = SchemaAPI(self)
        self.loaders = DataModelLoaderAPI(self)


@contextmanager
def monkeypatch_neat_client() -> Iterator[NeatClient]:
    neat_client_mock = NeatClientMock()
    NeatClient.__new__ = lambda *args, **kwargs: neat_client_mock  # type: ignore[method-assign]
    yield neat_client_mock
    NeatClient.__new__ = lambda cls, *args, **kwargs: object.__new__(cls)  # type: ignore[method-assign]
