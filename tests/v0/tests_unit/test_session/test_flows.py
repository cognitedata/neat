from collections.abc import Sequence

from cognite.client import data_modeling as dm

from cognite.neat import NeatSession
from cognite.neat.v0.core._client.data_classes.data_modeling import ContainerApplyDict, SpaceApplyDict, ViewApplyDict
from cognite.neat.v0.core._client.data_classes.schema import DMSSchema
from cognite.neat.v0.core._client.testing import monkeypatch_neat_client
from tests.v0.utils import as_read_containers, as_read_space


class TestImportExportFlow:
    def test_import_export_dms_with_cursorable(self) -> None:
        created_container: dm.ContainerApply | None = None
        with monkeypatch_neat_client() as client:
            my_space = dm.SpaceApply("my_space")
            my_container = dm.ContainerApply(
                space="my_space",
                external_id="my_container",
                properties={
                    "name": dm.ContainerProperty(dm.data_types.Text()),
                    "section": dm.ContainerProperty(dm.data_types.Text()),
                },
                indexes={
                    "nameindex": dm.containers.BTreeIndex(["name"], cursorable=True),
                    "combinedIndex": dm.containers.BTreeIndex(["section", "name"], cursorable=True),
                },
            )
            my_view = dm.ViewApply(
                space="my_space",
                external_id="my_view",
                properties={
                    "name": dm.MappedPropertyApply(my_container.as_id(), "name"),
                    "section": dm.MappedPropertyApply(my_container.as_id(), "section"),
                },
                version="v1",
            )
            my_model = dm.DataModelApply(space="my_space", external_id="my_model", views=[my_view], version="v1")
            schema = DMSSchema(
                my_model, SpaceApplyDict([my_space]), ViewApplyDict([my_view]), ContainerApplyDict([my_container])
            )

            read_model = schema.as_read_model()
            client.data_modeling.data_models.retrieve.return_value = dm.DataModelList([read_model])
            client.data_modeling.containers.retrieve.return_value = as_read_containers([my_container])
            client.data_modeling.spaces.retrieve.return_value = dm.SpaceList([as_read_space(my_space)])
            client.data_modeling.views.retrieve.return_value = dm.ViewList(read_model.views)

            def apply_container(containers: Sequence[dm.ContainerApply]) -> dm.Container:
                nonlocal created_container
                created_container = containers[0]
                return as_read_containers(containers)

            client.data_modeling.containers.apply.side_effect = apply_container

            neat = NeatSession(client)

        issues = neat.read.cdf.data_model(("my_space", "my_model", "v1"))
        assert len(issues) == 0

        _ = neat.to.cdf.data_model(existing="recreate", drop_data=True)

        assert created_container is not None
        indices = created_container.indexes
        assert "nameindex" in indices
        name_index = indices["nameindex"]
        assert isinstance(name_index, dm.containers.BTreeIndex)
        assert name_index.cursorable is True
        assert "combinedIndex" in indices
        combined_index = indices["combinedIndex"]
        assert isinstance(combined_index, dm.containers.BTreeIndex)
        assert combined_index.cursorable is True
        assert combined_index.properties == ["section", "name"]
