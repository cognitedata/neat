from cognite.neat._data_model.models.dms import SpaceRequest

from ._differ import ItemDiffer
from .data_classes import PropertyChange


class SpaceDiffer(ItemDiffer[SpaceRequest]):
    def diff(self, cdf_space: SpaceRequest, desired_space: SpaceRequest) -> list[PropertyChange]:
        return self._check_name_description(cdf_space, desired_space)
