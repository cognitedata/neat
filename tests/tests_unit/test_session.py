import contextlib
import io
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from cognite.neat import _state_machine as states
from cognite.neat._client import NeatClientConfig
from cognite.neat._issues import ImplementationWarning, IssueList
from cognite.neat._session._session import NeatSession


@pytest.fixture()
def new_session(neat_config: NeatClientConfig) -> NeatSession:
    return NeatSession(neat_config)


@pytest.fixture()
def physical_state_session(new_session: NeatSession, valid_dms_yaml_format: str) -> NeatSession:
    read_yaml = MagicMock(spec=Path)
    read_yaml.read_text.return_value = valid_dms_yaml_format

    new_session.physical_data_model.read.yaml(read_yaml)
    return new_session


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

    def test_read_data_model(self, valid_dms_yaml_format: str, new_session: NeatSession) -> None:
        session = new_session
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = valid_dms_yaml_format

        session.physical_data_model.read.yaml(read_yaml)
        assert len(session._store.physical_data_model) == 1
        assert len(session._store.provenance) == 1
        assert isinstance(session._store.state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].source_state, states.EmptyState)
        assert isinstance(session._store.provenance[-1].target_state, states.PhysicalState)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            session.issues()

        printed_statements = output.getvalue()
        assert "Non-Critical Issues" in str(printed_statements)

        by_type = cast(IssueList, new_session._store.provenance[-1].issues).by_type()
        assert set(by_type.keys()) == {ImplementationWarning}
        assert len(by_type[ImplementationWarning]) == 5

    def test_write_data_model(self, physical_state_session: NeatSession) -> None:
        session = physical_state_session
        write_yaml = MagicMock(spec=Path)

        session.physical_data_model.write.yaml(write_yaml)

        assert len(session._store.physical_data_model) == 1
        assert len(session._store.provenance) == 2
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
        assert len(session._store.provenance) == 1

        # we remain in physical state even though we hit Forbidden state, auto-recovery
        assert isinstance(session._store.state, states.PhysicalState)

    def test_write_again_data_model(self, physical_state_session: NeatSession) -> None:
        session = physical_state_session
        write_yaml = MagicMock(spec=Path)
        session.physical_data_model.write.yaml(write_yaml)

        assert len(session._store.physical_data_model) == 1
        assert len(session._store.provenance) == 2
        assert isinstance(session._store.state, states.PhysicalState)
        # there is no state change when writing
        assert isinstance(session._store.provenance[-1].source_state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].target_state, states.PhysicalState)
