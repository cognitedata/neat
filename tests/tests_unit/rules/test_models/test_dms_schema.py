from collections.abc import Iterable

import pytest
from _pytest.mark import ParameterSet
from cognite.client import data_modeling as dm

from cognite.neat.rules.models._rules.dms_schema import (
    ContainerPropertyUsedMultipleTimes,
    DirectRelationMissingSource,
    DMSSchema,
    DuplicatedViewInDataModel,
    MissingContainer,
    MissingContainerProperty,
    MissingEdgeView,
    MissingParentView,
    MissingSourceView,
    MissingSpace,
    MissingView,
    SchemaError,
)


def invalid_schema_test_cases() -> Iterable[ParameterSet]:
    my_space = dm.SpaceApply(space="my_space")
    data_model = dm.DataModelApply(
        space="my_space",
        external_id="my_data_model",
        version="1",
        views=[
            dm.ViewId("my_space", "my_view1", "1"),
            dm.ViewId("my_space", "my_view1", "1"),
        ],
    )
    yield pytest.param(
        DMSSchema(
            spaces=dm.SpaceApplyList([my_space]),
            data_models=dm.DataModelApplyList([data_model]),
        ),
        [
            DuplicatedViewInDataModel(
                view=dm.ViewId("my_space", "my_view1", "1"),
                referred_by=dm.DataModelId("my_space", "my_data_model", "1"),
            ),
            MissingView(
                view=dm.ViewId("my_space", "my_view1", "1"),
                referred_by=dm.DataModelId("my_space", "my_data_model", "1"),
            ),
        ],
        id="Duplicated and missing view in data model",
    )

    data_model = dm.DataModelApply(
        space="my_space",
        external_id="my_data_model",
        version="1",
        views=[
            dm.ViewId("my_space", "my_view1", "1"),
            dm.ViewId("my_space", "my_view2", "1"),
        ],
    )

    container = dm.ContainerApply(
        space="my_space",
        external_id="my_container",
        properties={
            "name": dm.ContainerProperty(
                type=dm.Text(),
            ),
            "value": dm.ContainerProperty(
                type=dm.Int32(),
            ),
        },
    )

    view1 = dm.ViewApply(
        space="my_space",
        external_id="my_view1",
        version="1",
        properties={
            "non_existing": dm.MappedPropertyApply(container.as_id(), "non_existing"),
            "name": dm.MappedPropertyApply(dm.ContainerId("my_space", "does_not_exist"), "name"),
        },
    )
    view2 = dm.ViewApply(
        space="my_space",
        external_id="my_view2",
        version="1",
        properties={
            "value": dm.MappedPropertyApply(container.as_id(), "value"),
            "value2": dm.MappedPropertyApply(container.as_id(), "value"),
        },
    )

    yield pytest.param(
        DMSSchema(
            spaces=dm.SpaceApplyList([my_space]),
            data_models=dm.DataModelApplyList([data_model]),
            views=dm.ViewApplyList([view1, view2]),
            containers=dm.ContainerApplyList([container]),
        ),
        [
            MissingContainer(
                container=dm.ContainerId("my_space", "does_not_exist"),
                referred_by=dm.ViewId("my_space", "my_view1", "1"),
            ),
            MissingContainerProperty(
                container=dm.ContainerId("my_space", "my_container"),
                property="non_existing",
                referred_by=dm.ViewId("my_space", "my_view1", "1"),
            ),
            ContainerPropertyUsedMultipleTimes(
                referred_by=frozenset(
                    {
                        (dm.ViewId("my_space", "my_view2", "1"), "value"),
                        (dm.ViewId("my_space", "my_view2", "1"), "value2"),
                    }
                ),
                container=dm.ContainerId("my_space", "my_container"),
                property="value",
            ),
        ],
        id="Missing container and properties. Container property used multiple times.",
    )

    my_data_model = dm.DataModelApply(
        space="my_space",
        external_id="my_data_model",
        version="1",
        views=[
            dm.ViewId("my_space", "my_view1", "1"),
        ],
    )
    container = dm.ContainerApply(
        space="non_existing_space",
        external_id="my_container",
        properties={
            "direct": dm.ContainerProperty(
                type=dm.DirectRelation(),
            ),
        },
    )

    view = dm.ViewApply(
        space="my_space",
        external_id="my_view1",
        version="1",
        properties={
            "direct": dm.MappedPropertyApply(container.as_id(), "direct"),
        },
    )

    yield pytest.param(
        DMSSchema(
            spaces=dm.SpaceApplyList([my_space]),
            data_models=dm.DataModelApplyList([my_data_model]),
            views=dm.ViewApplyList([view]),
            containers=dm.ContainerApplyList([container]),
        ),
        [
            MissingSpace(
                space="non_existing_space",
                referred_by=dm.ContainerId("non_existing_space", "my_container"),
            ),
            DirectRelationMissingSource(
                view_id=dm.ViewId("my_space", "my_view1", "1"),
                property="direct",
            ),
        ],
        id="Missing space, and direct relation missing source",
    )

    my_data_model = dm.DataModelApply(
        space="my_space",
        external_id="my_data_model",
        version="1",
        views=[
            dm.ViewId("my_space", "my_view1", "1"),
            dm.ViewId("my_space", "my_view2", "1"),
        ],
    )

    view1 = dm.ViewApply(
        space="my_space",
        external_id="my_view1",
        version="1",
        implements=[dm.ViewId("my_space", "non_existing", "1")],
        properties={
            "non_existing": dm.MultiEdgeConnectionApply(
                type=dm.DirectRelationReference("my_space", "external_id"),
                source=dm.ViewId("my_space", "non_existing", "1"),
                edge_source=dm.ViewId("my_space", "non_existing_edge_view", "1"),
            ),
        },
    )

    view2 = dm.ViewApply(
        space="my_space",
        external_id="my_view2",
        version="1",
        properties={
            "view1": dm.MultiEdgeConnectionApply(
                type=dm.DirectRelationReference("my_space", "external_id"),
                source=dm.ViewId("my_space", "my_view1", "1"),
            ),
        },
    )

    yield pytest.param(
        DMSSchema(
            spaces=dm.SpaceApplyList([my_space]),
            data_models=dm.DataModelApplyList([my_data_model]),
            views=dm.ViewApplyList([view1, view2]),
        ),
        [
            MissingParentView(
                view=dm.ViewId("my_space", "non_existing", "1"),
                referred_by=dm.ViewId("my_space", "my_view1", "1"),
            ),
            MissingEdgeView(
                view=dm.ViewId("my_space", "non_existing_edge_view", "1"),
                property="non_existing",
                referred_by=dm.ViewId("my_space", "my_view1", "1"),
            ),
            MissingSourceView(
                view=dm.ViewId("my_space", "non_existing", "1"),
                property="non_existing",
                referred_by=dm.ViewId("my_space", "my_view1", "1"),
            ),
        ],
        id="Missing parent view, edge view, and source view",
    )


class TestDMSSchema:
    @pytest.mark.parametrize(
        "schema, expected_errors",
        list(invalid_schema_test_cases()),
    )
    def test_invalid_schema(self, schema: DMSSchema, expected_errors: list[SchemaError]) -> None:
        errors = schema.validate()
        assert sorted(errors) == sorted(expected_errors)
