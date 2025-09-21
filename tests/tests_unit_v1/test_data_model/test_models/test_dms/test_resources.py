from collections.abc import Iterable

import pytest

from cognite.neat.core._utils.auxiliary import get_concrete_subclasses
from cognite.neat.data_model.models.dms import WriteableResource, Resource
from polyfactory.factories.pydantic_factory import ModelFactory


def all_concrete_resources() -> list[type[WriteableResource]]:
    return get_concrete_subclasses(WriteableResource, exclude_ABC_base=True)

class TestAsRequest:
    @pytest.mark.parametrize(
        "resource_cls", all_concrete_resources()
    )
    def test_writeable_resource_as_request(self, resource_cls: type[WriteableResource]) -> None:
        class ResourceFactory(ModelFactory[resource_cls]): ...
        instance = ResourceFactory.build()
        request_instance = instance.as_request()
        assert isinstance(request_instance, Resource)

