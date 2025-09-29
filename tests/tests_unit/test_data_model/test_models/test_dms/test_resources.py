import pytest
from polyfactory.factories.pydantic_factory import ModelFactory

from cognite.neat._data_model.models.dms import Resource, WriteableResource
from cognite.neat._utils.auxiliary import get_concrete_subclasses


def all_concrete_resources() -> list[type[WriteableResource]]:
    return get_concrete_subclasses(WriteableResource, exclude_direct_abc_inheritance=True)


@pytest.mark.skip(
    "Generating resource that are adhering to all the pydantic validation is not straight forward. "
    "Moved to task THIS-754"
)
class TestAsRequest:
    @pytest.mark.parametrize("resource_cls", all_concrete_resources())
    def test_writeable_resource_as_request(self, resource_cls: type[WriteableResource]) -> None:
        class ResourceFactory(ModelFactory[resource_cls]): ...  # type: ignore[valid-type]

        instance = ResourceFactory.build()
        # MyPy fails to understand that instance is a WriteableResource and not a type[WriteableResource]
        request_instance = instance.as_request()  # type: ignore[attr-defined]
        assert isinstance(request_instance, Resource)
