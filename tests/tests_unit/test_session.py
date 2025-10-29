import contextlib
import io
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
import respx

from cognite.neat import _state_machine as states
from cognite.neat._client import NeatClientConfig
from cognite.neat._data_model.importers import DMSAPIImporter, DMSImporter
from cognite.neat._data_model.models.dms import RequestSchema
from cognite.neat._issues import ConsistencyError, IssueList
from cognite.neat._session._physical import ReadPhysicalDataModel
from cognite.neat._session._session import NeatSession


@pytest.fixture()
def new_session(neat_config: NeatClientConfig, respx_mock: respx.MockRouter) -> NeatSession:
    session = NeatSession(neat_config)
    config = session._client.config
    respx_mock.post(
        config.create_api_url("/models/views/byids?includeInheritedProperties=true"),
    ).respond(
        status_code=200,
        json={
            "items": [],
            "nextCursor": None,
        },
    )

    return session


@pytest.fixture(scope="session")
def valid_dms_yaml_with_consistency_errors() -> str:
    return """Metadata:
- Key: space
  Value: my_space
- Key: externalId
  Value: TestModel
- Key: version
  Value: v1
Properties:
- View: MyDescribable
  View Property: name
  Value Type: text
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: cdf_cdm:CogniteDescribable
  Container Property: name
  Index: btree:name(cursorable=True)
  Connection: null
- View: MyDescribable
  View Property: source
  Connection: direct
  Value Type: cdf_cdm:UnexistingDirectConnection(version=v1)
  Min Count: 0
  Max Count: 1
  Immutable: false
  Container: cdf_cdm:CogniteSourceable
  Container Property: source
- View: MyDescribable
  View Property: singleEdgeProperty
  Connection: edge(type=MyDescribable.singleEdgeProperty)
  Value Type: cdf_cdm:UnexistingEdgeConnection(version=v1)
  Min Count: 0
  Max Count: 1
- View: MyDescribable
  View Property: reverseDirectProperty
  Connection: reverse(property=asset)
  Value Type: cdf_cdm:UnexistingReverseConnection(version=v1)
  Min Count: 0
  Max Count: 1
Views:
- View: MyDescribable
- View: MissingProperties
Containers:
- Container: cdf_cdm:CogniteDescribable
  Used For: node
- Container: cdf_cdm:CogniteSourceable
  Used For: node
"""


@pytest.fixture()
def physical_state_session(new_session: NeatSession, valid_dms_yaml_with_consistency_errors: str) -> NeatSession:
    read_yaml = MagicMock(spec=Path)
    read_yaml.read_text.return_value = valid_dms_yaml_with_consistency_errors

    new_session.physical_data_model.read.yaml(read_yaml)
    return new_session


@pytest.fixture()
def physical_written_session(physical_state_session: NeatSession) -> NeatSession:
    write_yaml = MagicMock(spec=Path)
    physical_state_session.physical_data_model.write.yaml(write_yaml)
    return physical_state_session


class TestNeatSession:
    def test_error_reading(self, new_session: NeatSession) -> None:
        session = new_session
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            session.physical_data_model.read.yaml("./invalid_path.yaml")

        printed_statements = output.getvalue()
        assert "No such file or directory" in str(printed_statements)
        assert len(session._store.physical_data_model) == 0
        assert len(session._store.provenance) == 0
        assert isinstance(session._store.state, states.EmptyState)

    def test_read_data_model(self, valid_dms_yaml_with_consistency_errors: str, new_session: NeatSession) -> None:
        session = new_session
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = valid_dms_yaml_with_consistency_errors

        session.physical_data_model.read.yaml(read_yaml)
        assert len(session._store.physical_data_model) == 1
        assert len(session._store.provenance) == 1
        assert isinstance(session._store.state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].source_state, states.EmptyState)
        assert isinstance(session._store.provenance[-1].target_state, states.PhysicalState)
        assert len(cast(IssueList, session._store.provenance[-1].issues)) == 4
        by_type = cast(IssueList, new_session._store.provenance[-1].issues).by_type()
        assert set(by_type.keys()) == {ConsistencyError}
        assert len(by_type[ConsistencyError]) == 4
        assert (
            "View my_space:MissingProperties(version=v1) does not have any properties defined"
            in by_type[ConsistencyError][0].message
        )

        for issue in by_type[ConsistencyError][1:]:
            assert "is not defined as a view in the data model niether exists in CDF" in issue.message

    def test_write_data_model(self, physical_state_session: NeatSession) -> None:
        session = physical_state_session
        write_yaml = MagicMock(spec=Path)

        provenance_before = len(session._store.provenance)
        session.physical_data_model.write.yaml(write_yaml)
        assert len(session._store.provenance) == provenance_before + 1

        assert len(session._store.physical_data_model) == 1
        assert isinstance(session._store.state, states.PhysicalState)
        # there is no state change when writing
        assert isinstance(session._store.provenance[-1].source_state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].target_state, states.PhysicalState)

    def test_forbid_read_in_physical_state(self, physical_state_session: NeatSession) -> None:
        session = physical_state_session
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = ""

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            session.physical_data_model.read.yaml(read_yaml)

        printed_statements = output.getvalue()
        assert "Cannot run DMSTableImporter in state PhysicalState" in str(printed_statements)
        assert len(session._store.physical_data_model) == 1

        # no change took place
        assert len(session._store.provenance) == 1, "We should only have the read change from before"

        # we remain in physical state even though we hit Forbidden state, auto-recovery
        assert isinstance(session._store.state, states.PhysicalState)

    def test_write_again_data_model(self, physical_written_session: NeatSession) -> None:
        session = physical_written_session
        write_yaml = MagicMock(spec=Path)

        provenance_before = len(session._store.provenance)
        session.physical_data_model.write.yaml(write_yaml)
        assert len(session._store.provenance) == provenance_before + 1

        assert len(session._store.physical_data_model) == 1
        assert isinstance(session._store.state, states.PhysicalState)
        # there is no state change when writing
        assert isinstance(session._store.provenance[-1].source_state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].target_state, states.PhysicalState)

    def test_read_dms_from_cdf(self, example_dms_schema: dict[str, Any], new_session: NeatSession) -> None:
        session = new_session
        mock_importer = MagicMock(spec=DMSAPIImporter)
        mock_importer.to_data_model.return_value = RequestSchema.model_validate(example_dms_schema)
        mock_importer.to_data_model.__name__ = DMSImporter.to_data_model.__name__

        provenance_before = len(session._store.provenance)

        with patch(
            f"{ReadPhysicalDataModel.__module__}.{DMSAPIImporter.__name__}.{DMSAPIImporter.from_cdf.__name__}",
            return_value=mock_importer,
        ):
            session.physical_data_model.read.cdf(space="test_space", external_id="test_id", version="v1")

        assert len(session._store.provenance) == provenance_before + 1
        assert len(session._store.physical_data_model) == 1
        assert isinstance(session._store.state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].source_state, states.EmptyState)
        assert isinstance(session._store.provenance[-1].target_state, states.PhysicalState)
