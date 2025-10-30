from cognite.neat._data_model.models.dms import SpaceRequest

from ._differ import ItemDiffer
from .data_classes import FieldChange


class SpaceDiffer(ItemDiffer[SpaceRequest]):
    def diff(self, cdf_space: SpaceRequest, desired_space: SpaceRequest) -> list[FieldChange]:
        return self._diff_name_description(cdf_space, desired_space)
