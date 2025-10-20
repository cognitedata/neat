from collections.abc import Sequence

from cognite.neat._data_model.models.dms import DataModelReference, DataModelResponse

from .api import NeatAPI


class DataModelsAPI(NeatAPI):
    def retrieve(
        self, data_model_id: DataModelReference | Sequence[DataModelReference]
    ) -> DataModelResponse | list[DataModelResponse]:
        raise NotImplementedError()

    def list(
        self, limit: int = 10, space: str | None = None, all_versions: bool = False, include_global: bool = False
    ) -> list[DataModelResponse]:
        raise NotImplementedError()
