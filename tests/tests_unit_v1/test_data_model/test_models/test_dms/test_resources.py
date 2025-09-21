import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from cognite.neat.core._utils.auxiliary import get_concrete_subclasses
from cognite.neat.data_model.models.dms import Resource, WriteableResource


def all_concrete_resources() -> list[type[WriteableResource]]:
    return get_concrete_subclasses(WriteableResource, exclude_ABC_base=True)  # type: ignore[type-abstract]


class TestAsRequest:
    @pytest.mark.parametrize("resource_cls", all_concrete_resources())
    def test_writeable_resource_as_request(self, resource_cls: type[WriteableResource]) -> None:
        class ResourceFactory(ModelFactory[resource_cls]): ...  # type: ignore[valid-type]

        instance = ResourceFactory.build()
        # MyPy fails to understand that instance is a WriteableResource and not a type[WriteableResource]
        request_instance = instance.as_request()  # type: ignore[attr-defined]
        assert isinstance(request_instance, Resource)
