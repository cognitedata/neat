import time
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

from cognite.neat._client import NeatClient
from cognite.neat._data_model._snapshot import SchemaCache, SchemaSnapshot
from cognite.neat._data_model.models.dms import (
    ContainerPropertyDefinition,
    ContainerReference,
    ContainerRequest,
    DataModelRequest,
    RequiresConstraintDefinition,
    TextProperty,
    ViewCorePropertyRequest,
    ViewReference,
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
    another_container = ContainerRequest(
        space="test_space",
        externalId="AnotherContainer",
        properties={
            "description": ContainerPropertyDefinition(type=TextProperty()),
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
                    container=another_container.as_reference(), containerPropertyIdentifier="description"
                ),
            },
            "implements": [ViewReference(space="cdf_cdm", external_id="CogniteVisualizable", version="v1")],
        },
    )
    data_model_two_views = data_model_one_view.model_copy(
        update={
            "views": [
                view_one_prop.as_reference(),
                other_view.as_reference(),
            ]
        }
    )
    container_no_constraints = ContainerRequest(
        space="test_space",
        externalId="MyContainer",
        properties={"name": ContainerPropertyDefinition(type=TextProperty())},
    )
    container_with_constraints = ContainerRequest(
        space="test_space",
        externalId="MyContainer",
        properties={"name": ContainerPropertyDefinition(type=TextProperty())},
        constraints={
            "requires_other": RequiresConstraintDefinition(
                require=ContainerReference(space="test_space", external_id="RequiredContainer")
            )
        },
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
            containers={container_one_prop.as_reference(): container_one_prop},
        ),
        SchemaSnapshot(
            timestamp=now,
            views={view_two_prop.as_reference(): view_two_prop},
            containers={
                container_one_prop.as_reference(): container_one_prop,
                another_container.as_reference(): another_container,
            },
        ),
        SchemaSnapshot(
            timestamp=now,
            views={view_two_prop.as_reference(): view_two_prop},
            containers={
                container_one_prop.as_reference(): container_one_prop,
                another_container.as_reference(): another_container,
            },
        ),
        id="CDF view has additional property and implements",
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
            views={view_one_prop.as_reference(): view_one_prop},
        ),
        SchemaSnapshot(
            timestamp=now,
            data_model={data_model_two_views.as_reference(): data_model_two_views},
            views={
                view_one_prop.as_reference(): view_one_prop,
                other_view.as_reference(): other_view,
            },
        ),
        SchemaSnapshot(
            timestamp=now,
            data_model={data_model_two_views.as_reference(): data_model_two_views},
            views={
                view_one_prop.as_reference(): view_one_prop,
                other_view.as_reference(): other_view,
            },
        ),
        id="CDF data model has additional view",
    )

    yield pytest.param(
        SchemaSnapshot(
            timestamp=now,
            containers={container_no_constraints.as_reference(): container_no_constraints},
        ),
        SchemaSnapshot(
            timestamp=now,
            containers={container_with_constraints.as_reference(): container_with_constraints},
        ),
        SchemaSnapshot(
            timestamp=now,
            containers={container_no_constraints.as_reference(): container_no_constraints},
        ),
        id="Local container constraints take precedence over CDF",
    )


class TestSchemaSnapshot:
    @pytest.mark.parametrize("local,cdf,expected", list(merge_schema_test_cases()))
    def test_merge_schema(self, local: SchemaSnapshot, cdf: SchemaSnapshot, expected: SchemaSnapshot) -> None:
        actual = local.merge(cdf)

        assert actual.model_dump() == expected.model_dump()


@pytest.fixture
def test_schemas() -> dict:
    """Provide test schemas from merge_schema_test_cases for reuse."""
    now = datetime.now(timezone.utc)
    container_one_prop = ContainerRequest(
        space="test_space",
        externalId="MyContainer",
        properties={
            "name": ContainerPropertyDefinition(type=TextProperty()),
        },
    )
    another_container = ContainerRequest(
        space="test_space",
        externalId="AnotherContainer",
        properties={
            "description": ContainerPropertyDefinition(type=TextProperty()),
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
    data_model_one_view = DataModelRequest(
        space="test_space",
        externalId="MyModel",
        version="v1",
        views=[view_one_prop.as_reference()],
    )

    return {
        "now": now,
        "container_one_prop": container_one_prop,
        "another_container": another_container,
        "view_one_prop": view_one_prop,
        "data_model_one_view": data_model_one_view,
    }


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock NeatClient."""
    client = MagicMock(spec=NeatClient)
    client.organization = "test_org"
    client.project = "test_project"
    return client


@pytest.fixture
def mock_snapshot(test_schemas: dict) -> SchemaSnapshot:
    """Create a mock SchemaSnapshot with test data."""
    return SchemaSnapshot(
        timestamp=test_schemas["now"],
        containers={test_schemas["container_one_prop"].as_reference(): test_schemas["container_one_prop"]},
        views={test_schemas["view_one_prop"].as_reference(): test_schemas["view_one_prop"]},
        data_model={test_schemas["data_model_one_view"].as_reference(): test_schemas["data_model_one_view"]},
    )


class TestSchemaCache:
    """Tests for SchemaCache functionality."""

    def test_init(self, mock_client: MagicMock) -> None:
        """Test SchemaCache initialization."""
        cache = SchemaCache(mock_client, max_cache_age_days=7)

        assert cache._client == mock_client
        assert cache._max_cache_age_days == 7
        assert cache._file.name == "test_org_test_project_snapshot.pkl"

    def test_init_default_max_cache_age(self, mock_client: MagicMock) -> None:
        """Test SchemaCache initialization with default max_cache_age_days."""
        cache = SchemaCache(mock_client)

        assert cache._max_cache_age_days == 1

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    def test_create_cache_directory(self, mock_cache_path: MagicMock, mock_client: MagicMock) -> None:
        """Test cache directory creation."""
        mock_dir = MagicMock(spec=Path)
        mock_cache_path.return_value = mock_dir

        cache = SchemaCache(mock_client)
        cache._create_cache_directory()

        mock_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    def test_exists_true(self, mock_cache_path: MagicMock, mock_client: MagicMock) -> None:
        """Test exists property when cache file exists."""
        mock_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = True
        mock_dir.__truediv__.return_value = mock_file
        mock_cache_path.return_value = mock_dir

        cache = SchemaCache(mock_client)

        assert cache.exists is True

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    def test_exists_false(self, mock_cache_path: MagicMock, mock_client: MagicMock) -> None:
        """Test exists property when cache file does not exist."""
        mock_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = False
        mock_dir.__truediv__.return_value = mock_file
        mock_cache_path.return_value = mock_dir

        cache = SchemaCache(mock_client)

        assert cache.exists is False

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    def test_is_valid_file_not_exists(self, mock_cache_path: MagicMock, mock_client: MagicMock) -> None:
        """Test is_valid property when cache file does not exist."""
        mock_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = False
        mock_dir.__truediv__.return_value = mock_file
        mock_cache_path.return_value = mock_dir

        cache = SchemaCache(mock_client)

        assert cache.is_valid is False

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    @patch("cognite.neat._data_model._snapshot.time")
    def test_is_valid_file_too_old(
        self, mock_time_module: MagicMock, mock_cache_path: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test is_valid property when cache file is too old."""
        mock_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = True
        mock_stat = MagicMock()
        mock_stat.st_mtime = 0  # Very old timestamp
        mock_file.stat.return_value = mock_stat
        mock_dir.__truediv__.return_value = mock_file
        mock_cache_path.return_value = mock_dir
        current_time = time.time()
        mock_time_module.time.return_value = current_time

        cache = SchemaCache(mock_client, max_cache_age_days=1)

        assert cache.is_valid is False

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    @patch("cognite.neat._data_model._snapshot.time")
    def test_is_valid_file_fresh(
        self, mock_time_module: MagicMock, mock_cache_path: MagicMock, mock_client: MagicMock
    ) -> None:
        """Test is_valid property when cache file is recent."""
        mock_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = True
        current_time = time.time()
        mock_stat = MagicMock()
        mock_stat.st_mtime = current_time - 3600  # 1 hour ago
        mock_file.stat.return_value = mock_stat
        mock_dir.__truediv__.return_value = mock_file
        mock_cache_path.return_value = mock_dir
        mock_time_module.time.return_value = current_time

        cache = SchemaCache(mock_client, max_cache_age_days=7)

        assert cache.is_valid is True

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    @patch("cognite.neat._data_model._snapshot.pickle.dump")
    @patch("cognite.neat._data_model._snapshot.SchemaSnapshot.fetch_entire_cdf")
    def test_create(
        self,
        mock_fetch: MagicMock,
        mock_pickle_dump: MagicMock,
        mock_cache_path: MagicMock,
        mock_client: MagicMock,
        mock_snapshot: SchemaSnapshot,
    ) -> None:
        """Test cache creation."""
        mock_fetch.return_value = mock_snapshot
        mock_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_file_open = mock_open()
        mock_dir.__truediv__.return_value = mock_file
        mock_cache_path.return_value = mock_dir

        cache = SchemaCache(mock_client)

        with patch.object(mock_file, "open", mock_file_open):
            cache.create()

        mock_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_fetch.assert_called_once_with(mock_client)
        mock_pickle_dump.assert_called_once()

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    @patch("cognite.neat._data_model._snapshot.pickle.load")
    def test_read_cache_exists_and_valid(
        self,
        mock_pickle_load: MagicMock,
        mock_cache_path: MagicMock,
        mock_client: MagicMock,
        mock_snapshot: SchemaSnapshot,
    ) -> None:
        """Test reading cache when it exists and is valid."""
        mock_pickle_load.return_value = mock_snapshot
        mock_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = True
        current_time = time.time()
        mock_stat = MagicMock()
        mock_stat.st_mtime = current_time - 3600
        mock_file.stat.return_value = mock_stat
        mock_file_open = mock_open()
        mock_dir.__truediv__.return_value = mock_file
        mock_cache_path.return_value = mock_dir

        cache = SchemaCache(mock_client, max_cache_age_days=7)

        with patch("cognite.neat._data_model._snapshot.time.time", return_value=current_time):
            with patch.object(mock_file, "open", mock_file_open):
                result = cache.read()

        assert result == mock_snapshot
        mock_pickle_load.assert_called_once()

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    @patch("cognite.neat._data_model._snapshot.SchemaSnapshot.fetch_entire_cdf")
    @patch("cognite.neat._data_model._snapshot.pickle.dump")
    @patch("cognite.neat._data_model._snapshot.pickle.load")
    @patch("cognite.neat._data_model._snapshot.time")
    def test_read_cache_not_exists(
        self,
        mock_time_module: MagicMock,
        mock_pickle_load: MagicMock,
        mock_pickle_dump: MagicMock,
        mock_fetch: MagicMock,
        mock_cache_path: MagicMock,
        mock_client: MagicMock,
        mock_snapshot: SchemaSnapshot,
    ) -> None:
        """Test reading cache when it does not exist - should create it."""
        mock_fetch.return_value = mock_snapshot
        mock_pickle_load.return_value = mock_snapshot
        current_time = time.time()
        mock_time_module.time.return_value = current_time

        mock_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        # File initially doesn't exist, then after create it exists
        mock_file.exists.side_effect = [False, True, True]
        # File modification time is fresh
        mock_stat = MagicMock()
        mock_stat.st_mtime = current_time - 3600
        mock_file.stat.return_value = mock_stat
        mock_file_open = mock_open()
        mock_dir.__truediv__.return_value = mock_file
        mock_cache_path.return_value = mock_dir

        cache = SchemaCache(mock_client)

        with patch.object(mock_file, "open", mock_file_open):
            result = cache.read()

        assert result == mock_snapshot
        mock_dir.mkdir.assert_called_with(parents=True, exist_ok=True)
        mock_fetch.assert_called_once_with(mock_client)

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    @patch("cognite.neat._data_model._snapshot.SchemaSnapshot.fetch_entire_cdf")
    @patch("cognite.neat._data_model._snapshot.pickle.dump")
    @patch("cognite.neat._data_model._snapshot.pickle.load")
    @patch("cognite.neat._data_model._snapshot.time")
    def test_read_cache_outdated(
        self,
        mock_time_module: MagicMock,
        mock_pickle_load: MagicMock,
        mock_pickle_dump: MagicMock,
        mock_fetch: MagicMock,
        mock_cache_path: MagicMock,
        mock_client: MagicMock,
        mock_snapshot: SchemaSnapshot,
    ) -> None:
        """Test reading cache when it is outdated - should update it."""
        mock_fetch.return_value = mock_snapshot
        mock_pickle_load.return_value = mock_snapshot
        current_time = time.time()
        mock_time_module.time.return_value = current_time

        mock_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = True
        mock_stat = MagicMock()
        mock_stat.st_mtime = current_time - (86400 * 10)  # 10 days ago
        mock_file.stat.return_value = mock_stat
        mock_file_open = mock_open()
        mock_dir.__truediv__.return_value = mock_file
        mock_cache_path.return_value = mock_dir

        cache = SchemaCache(mock_client, max_cache_age_days=1)

        with patch.object(mock_file, "open", mock_file_open):
            result = cache.read()

        assert result == mock_snapshot
        mock_file.unlink.assert_called_once()
        mock_fetch.assert_called_once_with(mock_client)

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    @patch("cognite.neat._data_model._snapshot.SchemaSnapshot.fetch_entire_cdf")
    @patch("cognite.neat._data_model._snapshot.pickle.dump")
    def test_update(
        self,
        mock_pickle_dump: MagicMock,
        mock_fetch: MagicMock,
        mock_cache_path: MagicMock,
        mock_client: MagicMock,
        mock_snapshot: SchemaSnapshot,
    ) -> None:
        """Test cache update (delete and recreate)."""
        mock_fetch.return_value = mock_snapshot
        mock_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = True
        mock_file_open = mock_open()
        mock_dir.__truediv__.return_value = mock_file
        mock_cache_path.return_value = mock_dir

        cache = SchemaCache(mock_client)

        with patch.object(mock_file, "open", mock_file_open):
            cache.update()

        mock_file.unlink.assert_called()
        mock_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_fetch.assert_called_once_with(mock_client)

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    def test_delete_file_exists(self, mock_cache_path: MagicMock, mock_client: MagicMock) -> None:
        """Test deleting cache when file exists."""
        mock_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = True
        mock_dir.__truediv__.return_value = mock_file
        mock_cache_path.return_value = mock_dir

        cache = SchemaCache(mock_client)
        cache.delete()

        mock_file.unlink.assert_called_once()

    @patch("cognite.neat._data_model._snapshot.user_cache_path")
    def test_delete_file_not_exists(self, mock_cache_path: MagicMock, mock_client: MagicMock) -> None:
        """Test deleting cache when file does not exist."""
        mock_dir = MagicMock(spec=Path)
        mock_file = MagicMock(spec=Path)
        mock_file.exists.return_value = False
        mock_dir.__truediv__.return_value = mock_file
        mock_cache_path.return_value = mock_dir

        cache = SchemaCache(mock_client)
        cache.delete()

        mock_file.unlink.assert_not_called()

    def test_cache_filename_format(self, mock_client: MagicMock) -> None:
        """Test that cache filename follows the expected format."""
        cache = SchemaCache(mock_client)

        expected_filename = "test_org_test_project_snapshot.pkl"
        assert cache._file.name == expected_filename
