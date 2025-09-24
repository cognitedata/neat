from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import MagicMock

from cognite.client.testing import CogniteClientMock

from cognite.neat.v0.core._client._api_client import NeatClient

from ._api.data_modeling_loaders import DataModelLoaderAPI
from ._api.neat_instances import NeatInstancesAPI
from ._api.schema import SchemaAPI
from ._api.statistics import StatisticsAPI


class NeatClientMock(CogniteClientMock):
    """Mock for ToolkitClient object

    All APIs are replaced with specked MagicMock objects.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if "parent" in kwargs:
            super().__init__(*args, **kwargs)
            return
        super().__init__(*args, **kwargs)
        self.instance_statistics = MagicMock(spec_set=StatisticsAPI)

        self.schema = SchemaAPI(self)
        self.loaders = DataModelLoaderAPI(self)
        self.instances = NeatInstancesAPI(self)


@contextmanager
def monkeypatch_neat_client() -> Iterator[NeatClient]:
    neat_client_mock = NeatClientMock()
    NeatClient.__new__ = lambda *args, **kwargs: neat_client_mock  # type: ignore[method-assign]
    yield neat_client_mock
    NeatClient.__new__ = lambda cls, *args, **kwargs: object.__new__(cls)  # type: ignore[method-assign]
