from cognite.client import data_modeling as dm

from cognite.neat._client._api.data_modeling_loaders import DataModelLoader

_DEFAULT_ARGS = dict(is_global=False, created_time=1, last_updated_time=1, name=None, description=None)


class TestDataModelLoader:
    def test_merge_data_models(self) -> None:
        local = dm.DataModelApply(
            "my_space",
            "my_model",
            "v1",
            views=[
                dm.ViewId("my_space", "view1", "v1"),
            ],
        )
        remote = dm.DataModel[dm.ViewId](
            "my_space",
            "my_model",
            "v1",
            views=[
                dm.ViewId("my_space", "view2", "v1"),
            ],
            **_DEFAULT_ARGS,
        )

        merged = DataModelLoader.merge(local, remote)

        assert merged == dm.DataModelApply(
            "my_space",
            "my_model",
            "v1",
            views=[
                dm.ViewId("my_space", "view1", "v1"),
                dm.ViewId("my_space", "view2", "v1"),
            ],
        )
