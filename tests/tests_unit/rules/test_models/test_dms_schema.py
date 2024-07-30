import warnings
from collections.abc import Iterable
from pathlib import Path

import pytest
from _pytest.mark import ParameterSet
from cognite.client import data_modeling as dm
from cognite.client.data_classes import DatabaseWrite, DatabaseWriteList, TransformationWrite, TransformationWriteList

from cognite.neat.issues import NeatError, NeatIssue, NeatWarning
from cognite.neat.issues.errors.properties import ReferredPropertyNotFoundError
from cognite.neat.issues.errors.resources import ReferredResourceNotFoundError
from cognite.neat.issues.neat_warnings.external import UnexpectedFileTypeWarning
from cognite.neat.issues.neat_warnings.models import UserModelingWarning
from cognite.neat.rules.issues.dms import (
    DuplicatedViewInDataModelError,
)
from cognite.neat.rules.models import DMSSchema
from cognite.neat.rules.models.dms import PipelineSchema
from cognite.neat.utils.cdf.data_classes import (
    ContainerApplyDict,
    RawTableWrite,
    RawTableWriteList,
    SpaceApplyDict,
    ViewApplyDict,
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
            spaces=SpaceApplyDict([my_space]),
            data_model=data_model,
        ),
        [
            DuplicatedViewInDataModelError(
                view=dm.ViewId("my_space", "my_view1", "1"),
                referred_by=dm.DataModelId("my_space", "my_data_model", "1"),
            ),
            ReferredResourceNotFoundError[dm.ViewId, dm.DataModelId](
                dm.ViewId("my_space", "my_view1", "1"),
                "View",
                dm.DataModelId("my_space", "my_data_model", "1"),
                "DataModel",
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
            spaces=SpaceApplyDict([my_space]),
            data_model=data_model,
            views=ViewApplyDict([view1, view2]),
            containers=ContainerApplyDict([container]),
        ),
        [
            ReferredResourceNotFoundError[dm.ContainerId, dm.ViewId](
                dm.ContainerId("my_space", "does_not_exist"),
                "Container",
                dm.ViewId("my_space", "my_view1", "1"),
                "View",
            ),
            ReferredPropertyNotFoundError[dm.ContainerId, dm.ViewId](
                dm.ContainerId("my_space", "my_container"),
                "Container",
                dm.ViewId("my_space", "my_view1", "1"),
                "View",
                "non_existing",
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
            spaces=SpaceApplyDict([my_space]),
            data_model=my_data_model,
            views=ViewApplyDict([view]),
            containers=ContainerApplyDict([container]),
        ),
        [
            ReferredResourceNotFoundError[str, dm.ContainerId](
                identifier="non_existing_space",
                resource_type="Space",
                referred_by=dm.ContainerId("non_existing_space", "my_container"),
                referred_type="Container",
            ),
            UserModelingWarning(
                "DirectRelationMissingSource",
                f"The view {dm.ViewId('my_space', 'my_view1', '1')!r}.direct is a direct relation without a source",
                "Direct relations in views should point to a single other view, if not,"
                "you end up with a more complex schema than necessary.",
                "Create the source view",
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
            spaces=SpaceApplyDict([my_space]),
            data_model=my_data_model,
            views=ViewApplyDict([view1, view2]),
        ),
        [
            ReferredPropertyNotFoundError[dm.ViewId, dm.ViewId](
                dm.ViewId("my_space", "non_existing", "1"),
                "View",
                dm.ViewId("my_space", "my_view1", "1"),
                "View",
                property_name="implements",
            ),
            ReferredPropertyNotFoundError[dm.ViewId, dm.ViewId](
                dm.ViewId("my_space", "non_existing", "1"),
                "View",
                dm.ViewId("my_space", "my_view1", "1"),
                "View",
                property_name="non_existing",
            ),
            ReferredPropertyNotFoundError[dm.ViewId, dm.ViewId](
                dm.ViewId("my_space", "non_existing_edge_view", "1"),
                "View",
                dm.ViewId("my_space", "my_view1", "1"),
                "View",
                property_name="non_existing",
            ),
        ],
        id="Missing parent view, edge view, and source view",
    )


def valid_schema_test_cases() -> Iterable[ParameterSet]:
    dms_schema = DMSSchema(
        spaces=SpaceApplyDict([dm.SpaceApply(space="my_space")]),
        data_model=dm.DataModelApply(
            space="my_space",
            external_id="my_data_model",
            version="1",
            views=[
                dm.ViewId("my_space", "my_view1", "1"),
                dm.ViewId("my_space", "my_view2", "1"),
            ],
        ),
        containers=ContainerApplyDict(
            [
                dm.ContainerApply(
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
            ]
        ),
        views=ViewApplyDict(
            [
                dm.ViewApply(
                    space="my_space",
                    external_id="my_view1",
                    version="1",
                    properties={
                        "name": dm.MappedPropertyApply(dm.ContainerId("my_space", "my_container"), "name"),
                    },
                ),
                dm.ViewApply(
                    space="my_space",
                    external_id="my_view2",
                    version="1",
                    properties={
                        "value": dm.MappedPropertyApply(dm.ContainerId("my_space", "my_container"), "value"),
                    },
                ),
            ]
        ),
    )
    yield pytest.param(dms_schema, id="DMS schema")

    pipeline_schema = PipelineSchema(
        # Serializing to ensure that we are copying the object
        spaces=SpaceApplyDict.load(dms_schema.spaces.dump()),
        data_model=dm.DataModelApply.load(dms_schema.data_model.dump()),
        containers=ContainerApplyDict.load(dms_schema.containers.dump()),
        views=ViewApplyDict.load(dms_schema.views.dump()),
        transformations=TransformationWriteList(
            [TransformationWrite(external_id="my_transformation", ignore_null_fields=True, name="My transformation")]
        ),
        databases=DatabaseWriteList([DatabaseWrite(name="my_database")]),
        raw_tables=RawTableWriteList([RawTableWrite(name="my_raw_table", database="my_database")]),
    )
    yield pytest.param(pipeline_schema, id="Pipeline schema")


def invalid_raw_str_test_cases() -> Iterable[ParameterSet]:
    raw_str = """
    views:
      - space: my_space
        externalId: my_view1
        version: 1
        properties: {}
    """
    yield pytest.param(raw_str, {"views": [Path("my_view_file.yaml")]}, [], id="No issues")
    raw_str = """
    views:
      - space: my_space
        external_id: my_view1
        version: 1
        properties: {}
    """
    yield pytest.param(
        raw_str,
        {"views": [Path("my_view_file.yaml")]},
        [
            UnexpectedFileTypeWarning(
                Path("my_view_file.yaml"),
                ["ViewApply"],
                "KeyError('externalId')",
            )
        ],
        id="Misspelled external_id",
    )


class TestDMSSchema:
    @pytest.mark.parametrize(
        "schema, expected",
        list(invalid_schema_test_cases()),
    )
    def test_invalid_schema(self, schema: DMSSchema, expected: list[NeatIssue]) -> None:
        expected_errors = [error for error in expected if isinstance(error, NeatError)]
        expected_warnings = [warning for warning in expected if isinstance(warning, NeatWarning)]
        with warnings.catch_warnings(record=True) as warning_logger:
            errors = schema.validate()
        assert set(errors) == set(expected_errors)
        actual_warnings = [warning.message for warning in warning_logger]
        assert set(actual_warnings) == set(expected_warnings)

    @pytest.mark.parametrize(
        "schema",
        list(valid_schema_test_cases()),
    )
    def test_dump_load_schema(self, schema: DMSSchema) -> None:
        dumped_schema = schema.dump()
        loaded_schema = PipelineSchema.load(dumped_schema)
        assert schema.dump() == loaded_schema.dump()

    @pytest.mark.parametrize(
        "schema",
        list(valid_schema_test_cases()),
    )
    def test_as_read_model(self, schema: DMSSchema) -> None:
        read_model = schema.as_read_model()
        assert isinstance(read_model, dm.DataModel)

    @pytest.mark.parametrize(
        "schema",
        list(valid_schema_test_cases()),
    )
    def test_to_and_from_directory(self, schema: DMSSchema, tmp_path: Path) -> None:
        schema.to_directory(tmp_path)
        loaded_schema = PipelineSchema.from_directory(tmp_path)
        assert schema.dump() == loaded_schema.dump()

    @pytest.mark.parametrize(
        "schema",
        list(valid_schema_test_cases()),
    )
    def test_to_and_from_zip(self, schema: DMSSchema, tmp_path: Path) -> None:
        schema.to_zip(tmp_path / "schema.zip")
        loaded_schema = PipelineSchema.from_zip(tmp_path / "schema.zip")
        assert schema.dump() == loaded_schema.dump()

    @pytest.mark.parametrize(
        "raw_str, context, expected_issues",
        list(invalid_raw_str_test_cases()),
    )
    def test_load_invalid_raw_str(
        self, raw_str: str, context: dict[str, list[Path]], expected_issues: list[NeatIssue]
    ) -> None:
        with warnings.catch_warnings(record=True) as warning_logger:
            _ = DMSSchema.load(raw_str, context)
        actual_warnings = [warning.message for warning in warning_logger]
        assert sorted(actual_warnings) == sorted(expected_issues)
