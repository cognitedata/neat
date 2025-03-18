import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any, Literal

from cognite.client.data_classes.data_modeling import Edge, Node, ViewId
from cognite.client.data_classes.filters import Filter
from cognite.client.exceptions import CogniteAPIError
from cognite.client.utils.useful_types import SequenceNotStr

if TYPE_CHECKING:
    from cognite.neat._client._api_client import NeatClient


class NeatInstancesAPI:
    def __init__(self, client: "NeatClient") -> None:
        self._client = client

    def iterate(
        self,
        instance_type: Literal["node", "edge"] = "node",
        space: str | SequenceNotStr[str] | None = None,
        filter_: Filter | None = None,
        source: ViewId | None = None,
    ) -> Iterator[Node] | Iterator[Edge]:
        """Neat specific implementation of the client.data_modeling.instances(...) method to account for 408.

        In addition, we enforce sort based on the argument below (provided by Alex B.).
        """
        body: dict[str, Any] = {"limit": 1_000, "cursor": None, "instanceType": instance_type}
        # Without a sort, the sort is implicitly by the internal id, as cursoring needs a stable sort.
        # By making the sort be on external_id, Postgres should pick the index that's on
        # (project_id, space, external_id) WHERE deleted_at IS NULL. In other words,
        # avoiding soft deleted instances.
        body["sort"] = [
            {
                "property": [instance_type, "externalId"],
                "direction": "ascending",
            }
        ]
        url = f"/api/{self._client._API_VERSION}/projects/{self._client.config.project}/models/instances/list"
        filter_ = self._client.data_modeling.instances._merge_space_into_filter(instance_type, space, filter_)
        if filter_:
            body["filter"] = filter_.dump() if isinstance(filter_, Filter) else filter_
        if source:
            body["sources"] = [{"source": source.dump(include_type=True, camel_case=True)}]
        last_limit_change: float = 0.0
        while True:
            try:
                response = self._client.post(url=url, json=body)
            except CogniteAPIError as e:
                if e.code == 408 and body["limit"] > 1:
                    body["limit"] = body["limit"] // 2
                    last_limit_change = time.perf_counter()
                    continue
                raise e
            response_body = response.json()
            yield from (
                Node.load(item) if item.get("instanceType") == "node" else Edge.load(item)
                for item in response_body["items"]
            )
            next_cursor = response_body.get("nextCursor")
            if next_cursor is None:
                break
            body["cursor"] = next_cursor
            # Increase the limit every 30 seconds to avoid fetching reduced
            # instances for a long time after a 408. This limit is somewhat arbitrary,
            # but it should be large enough to avoid many requests, but small enough
            # to avoid fetching very slowly for a long time after a 408.
            if (time.perf_counter() - last_limit_change) > 30.0 and body["limit"] < 1_000:
                body["limit"] = min(int(body["limit"] * 1.5), 1_000)
                last_limit_change = time.perf_counter()
