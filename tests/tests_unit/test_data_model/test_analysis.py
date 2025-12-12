from collections.abc import Iterator
from datetime import datetime

import pytest

from cognite.neat._data_model._analysis import ValidationResources
from cognite.neat._data_model.deployer.data_classes import SchemaSnapshot
from cognite.neat._data_model.models.dms import (
    ContainerPropertyDefinition,
    ContainerRequest,
    DataModelRequest,
    TextProperty,
    ViewCorePropertyRequest,
    ViewRequest,
)


def merge_schema_test_cases() -> Iterator[tuple]:
    # Test case 1: Both local and cdf are empty
    now = datetime.now()
    container_one_prop = ContainerRequest(
        space="test_space",
        externalId="MyContainer",
        properties={
            "name": ContainerPropertyDefinition(type=TextProperty()),
        },
    )
    view_one_prop = ViewRequest(
        space="test_space",
        externalId="MyView",
        version="v1",
        properties={
            "name": ViewCorePropertyRequest(
                container=container_one_prop.as_reference(), containerPropertyIdentifier="name"
            ),
        },
    )
    other_view = ViewRequest(
        space="test_space",
        externalId="OtherView",
        version="v1",
        properties={
            "name": ViewCorePropertyRequest(
                container=container_one_prop.as_reference(), containerPropertyIdentifier="name"
            ),
        },
    )
    data_model_one_view = DataModelRequest(
        space="test_space",
        externalId="MyModel",
        version="v1",
        views=[view_one_prop.as_reference()],
    )
    container_two_prop = container_one_prop.model_copy(
        update={
            "properties": {
                "name": ContainerPropertyDefinition(type=TextProperty()),
                "description": ContainerPropertyDefinition(type=TextProperty()),
            }
        }
    )
    view_two_prop = view_one_prop.model_copy(
        update={
            "properties": {
                "name": ViewCorePropertyRequest(
                    container=container_two_prop.as_reference(), containerPropertyIdentifier="name"
                ),
                "description": ViewCorePropertyRequest(
                    container=container_two_prop.as_reference(), containerPropertyIdentifier="description"
                ),
            }
        }
    )
    data_model_two_views = data_model_one_view.model_copy(
        update={
            "views": [
                view_one_prop.as_reference(),
                other_view.as_reference(),
            ]
        }
    )
    yield pytest.param(
        SchemaSnapshot(timestamp=now),
        SchemaSnapshot(timestamp=now),
        SchemaSnapshot(timestamp=now),
        id="Both local and cdf are empty",
    )
    yield pytest.param(
        SchemaSnapshot(
            timestamp=now,
            containers={container_one_prop.as_reference(): container_one_prop},
        ),
        SchemaSnapshot(timestamp=now),
        SchemaSnapshot(
            timestamp=now,
            containers={container_one_prop.as_reference(): container_one_prop},
        ),
        id="Local has one container, CDF is empty",
    )
    yield pytest.param(
        SchemaSnapshot(
            timestamp=now,
            containers={container_one_prop.as_reference(): container_one_prop},
        ),
        SchemaSnapshot(
            timestamp=now,
            containers={container_two_prop.as_reference(): container_two_prop},
        ),
        SchemaSnapshot(
            timestamp=now,
            containers={container_two_prop.as_reference(): container_two_prop},
        ),
        id="CDF container has additional property",
    )
    yield pytest.param(
        SchemaSnapshot(
            timestamp=now,
            views={view_one_prop.as_reference(): view_one_prop},
        ),
        SchemaSnapshot(timestamp=now),
        SchemaSnapshot(
            timestamp=now,
            views={view_one_prop.as_reference(): view_one_prop},
        ),
        id="Local has one view, CDF is empty",
    )
    yield pytest.param(
        SchemaSnapshot(
            timestamp=now,
            views={view_one_prop.as_reference(): view_one_prop},
        ),
        SchemaSnapshot(
            timestamp=now,
            views={view_two_prop.as_reference(): view_two_prop},
        ),
        SchemaSnapshot(
            timestamp=now,
            views={view_two_prop.as_reference(): view_two_prop},
        ),
        id="CDF view has additional property",
    )

    yield pytest.param(
        SchemaSnapshot(
            timestamp=now,
            data_model={data_model_one_view.as_reference(): data_model_one_view},
        ),
        SchemaSnapshot(timestamp=now),
        SchemaSnapshot(
            timestamp=now,
            data_model={data_model_one_view.as_reference(): data_model_one_view},
        ),
        id="Local has one data model, CDF is empty",
    )
    yield pytest.param(
        SchemaSnapshot(
            timestamp=now,
            data_model={data_model_one_view.as_reference(): data_model_one_view},
        ),
        SchemaSnapshot(
            timestamp=now,
            data_model={data_model_two_views.as_reference(): data_model_two_views},
        ),
        SchemaSnapshot(
            timestamp=now,
            data_model={data_model_two_views.as_reference(): data_model_two_views},
        ),
        id="CDF data model has additional view",
    )


class TestValidationResources:
    @pytest.mark.parametrize("local,cdf,expected", list(merge_schema_test_cases()))
    def test_merge_schema(self, local: SchemaSnapshot, cdf: SchemaSnapshot, expected: SchemaSnapshot) -> None:
        actual = ValidationResources.merge(local, cdf)

        assert actual.model_dump() == expected.model_dump()
