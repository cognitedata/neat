from collections.abc import Iterable

from cognite.client.data_classes.data_modeling.instances import Instance

from cognite.neat.graph.models import Triple

from ._base import BaseExtractor


class DMSExtractor(BaseExtractor):
    """Extract data from Cognite Data Fusion DMS instances into Neat."""

    def __init__(self, items: Iterable[Instance], total: int | None = None, limit: int | None = None) -> None:
        self.items = items
        self.total = total
        self.limit = limit

    def extract(self) -> Iterable[Triple]:
        for count, item in enumerate(self.items, 1):
            if self.limit and count > self.limit:
                break
            yield from self._extract_instance(item)

    def _extract_instance(self, instance: Instance) -> Iterable[Triple]:
        raise NotImplementedError()
