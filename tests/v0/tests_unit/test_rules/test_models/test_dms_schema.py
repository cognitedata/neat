import warnings
from collections.abc import Iterable
from pathlib import Path

import pytest
from _pytest.mark import ParameterSet
from cognite.client import data_modeling as dm

from cognite.neat.v0.core._client.data_classes.data_modeling import (
    ContainerApplyDict,
    SpaceApplyDict,
    ViewApplyDict,
)
from cognite.neat.v0.core._data_model.models import DMSSchema
from cognite.neat.v0.core._data_model.models.physical import PhysicalValidation
from cognite.neat.v0.core._issues import NeatError, NeatIssue, NeatWarning
from cognite.neat.v0.core._issues.errors import (
    PropertyNotFoundError,
    ResourceDuplicatedError,
    ResourceNotFoundError,
)
from cognite.neat.v0.core._issues.warnings import FileTypeUnexpectedWarning
from cognite.neat.v0.core._issues.warnings.user_modeling import (
    DirectRelationMissingSourceWarning,
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
            ResourceDuplicatedError(
                identifier=dm.ViewId("my_space", "my_view1", "1"),
                resource_type="view",
                location=f"DMS {dm.DataModelId('my_space', 'my_data_model', '1')!r}",
            ),
            ResourceNotFoundError(
                dm.ViewId("my_space", "my_view1", "1"),
                "view",
                dm.DataModelId("my_space", "my_data_model", "1"),
                "data model",
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
            ResourceNotFoundError(
                dm.ContainerId("my_space", "does_not_exist"),
                "container",
                dm.ViewId("my_space", "my_view1", "1"),
                "view",
            ),
            PropertyNotFoundError(
                dm.ContainerId("my_space", "my_container"),
                "container",
                "non_existing",
                dm.ViewId("my_space", "my_view1", "1"),
                "view",
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
            ResourceNotFoundError(
                identifier="non_existing_space",
                resource_type="space",
                referred_by=dm.ContainerId("non_existing_space", "my_container"),
                referred_type="container",
            ),
            DirectRelationMissingSourceWarning(
                dm.ViewId("my_space", "my_view1", "1"),
                "direct",
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
            PropertyNotFoundError(
                dm.ViewId("my_space", "non_existing", "1"),
                "view",
                "implements",
                dm.ViewId("my_space", "my_view1", "1"),
                "view",
            ),
            PropertyNotFoundError(
                dm.ViewId("my_space", "non_existing", "1"),
                "view",
                "non_existing",
                dm.ViewId("my_space", "my_view1", "1"),
                "view",
            ),
            PropertyNotFoundError(
                dm.ViewId("my_space", "non_existing_edge_view", "1"),
                "view",
                "non_existing",
                dm.ViewId("my_space", "my_view1", "1"),
                "view",
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
            FileTypeUnexpectedWarning(
                Path("my_view_file.yaml"),
                frozenset(["ViewApply"]),
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
            errors = PhysicalValidation._validate_schema(schema, dict(schema.views), dict(schema.containers))
        assert set(errors) == set(expected_errors)
        actual_warnings = [warning.message for warning in warning_logger]
        assert set(actual_warnings) == set(expected_warnings)

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
        loaded_schema = DMSSchema.from_directory(tmp_path)
        assert schema.dump() == loaded_schema.dump()

    @pytest.mark.parametrize(
        "schema",
        list(valid_schema_test_cases()),
    )
    def test_to_and_from_zip(self, schema: DMSSchema, tmp_path: Path) -> None:
        schema.to_zip(tmp_path / "schema.zip")
        loaded_schema = DMSSchema.from_zip(tmp_path / "schema.zip")
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

    def test_load_from_read_model(self) -> None:
        default_model_args = dict(
            last_updated_time=1,
            created_time=1,
            description=None,
            name=None,
            is_global=False,
        )
        default_view_args = dict(
            filter=None,
            implements=None,
            writable=True,
            used_for="node",
            **default_model_args,
        )
        default_prop_args = dict(
            nullable=True,
            immutable=False,
            name=None,
            description=None,
            source=None,
            auto_increment=False,
            default_value=None,
        )
        read_model = dm.DataModel(
            space="my_space",
            external_id="my_data_model",
            version="1",
            views=[
                dm.View(
                    space="my_space",
                    external_id="my_view1",
                    version="1",
                    properties={
                        "name": dm.MappedProperty(
                            dm.ContainerId("my_space", "my_container"), "name", dm.Text(), **default_prop_args
                        ),
                    },
                    **default_view_args,
                ),
                dm.View(
                    space="my_space",
                    external_id="my_view2",
                    version="1",
                    properties={
                        "value": dm.MappedProperty(
                            dm.ContainerId("my_space", "my_container"), "value", dm.Float64(), **default_prop_args
                        ),
                    },
                    **default_view_args,
                ),
            ],
            **default_model_args,
        )
        schema = DMSSchema.from_read_model(read_model)
        assert schema.dump() == {
            "containers": [
                {
                    "constraints": {},
                    "externalId": "my_container",
                    "indexes": {},
                    "properties": {
                        "name": {
                            "autoIncrement": False,
                            "immutable": False,
                            "nullable": True,
                            "type": {"collation": "ucs_basic", "list": False, "type": "text"},
                        },
                        "value": {
                            "autoIncrement": False,
                            "immutable": False,
                            "nullable": True,
                            "type": {"list": False, "type": "float64"},
                        },
                    },
                    "space": "my_space",
                    "usedFor": "node",
                }
            ],
            "dataModel": {
                "externalId": "my_data_model",
                "space": "my_space",
                "version": "1",
                "views": [
                    {"externalId": "my_view1", "space": "my_space", "type": "view", "version": "1"},
                    {"externalId": "my_view2", "space": "my_space", "type": "view", "version": "1"},
                ],
            },
            "spaces": [{"space": "my_space"}],
            "views": [
                {
                    "externalId": "my_view1",
                    "implements": [],
                    "properties": {
                        "name": {
                            "container": {"externalId": "my_container", "space": "my_space", "type": "container"},
                            "containerPropertyIdentifier": "name",
                        }
                    },
                    "space": "my_space",
                    "version": "1",
                },
                {
                    "externalId": "my_view2",
                    "implements": [],
                    "properties": {
                        "value": {
                            "container": {"externalId": "my_container", "space": "my_space", "type": "container"},
                            "containerPropertyIdentifier": "value",
                        }
                    },
                    "space": "my_space",
                    "version": "1",
                },
            ],
        }
