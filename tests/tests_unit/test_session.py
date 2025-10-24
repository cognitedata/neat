import contextlib
import io
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock

import pytest

from cognite.neat import _state_machine as states
from cognite.neat._issues import ImplementationWarning, IssueList
from cognite.neat._session._session import NeatSession
from tests.tests_unit.test_data_model.test_importers.test_dms_table_importer import valid_dms_yaml_formats

session = NeatSession()


class TestNeatSession:
    def test_error_reading(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            session.physical_data_model.read.yaml("./invalid_path.yaml")

        printed_statements = output.getvalue()
        assert "No such file or directory" in str(printed_statements)
        assert len(session._store.physical_data_model) == 0
        assert len(session._store.provenance) == 0
        assert isinstance(session._store.state, states.EmptyState)

    @pytest.mark.parametrize("yaml_str", list(valid_dms_yaml_formats()))
    def test_read_data_model(self, yaml_str: str) -> None:
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = yaml_str

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

        by_type = cast(IssueList, session._store.provenance[-1].issues).by_type()
        assert set(by_type.keys()) == {ImplementationWarning}
        assert len(by_type[ImplementationWarning]) == 5

    def test_write_data_model(self) -> None:
        write_yaml = MagicMock(spec=Path)

        session.physical_data_model.write.yaml(write_yaml)

        assert len(session._store.physical_data_model) == 1
        assert len(session._store.provenance) == 2
        assert isinstance(session._store.state, states.PhysicalState)
        # there is no state change when writing
        assert isinstance(session._store.provenance[-1].source_state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].target_state, states.PhysicalState)

    def test_forbid_read_in_physical_state(self) -> None:
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = ""

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            session.physical_data_model.read.yaml(read_yaml)

        printed_statements = output.getvalue()
        assert "Cannot run DMSTableImporter in state PhysicalState" in str(printed_statements)
        assert len(session._store.physical_data_model) == 1

        # no change took place
        assert len(session._store.provenance) == 2

        # we remain in physical state even though we hit Forbidden state, auto-recovery
        assert isinstance(session._store.state, states.PhysicalState)

    def test_write_again_data_model(self) -> None:
        write_yaml = MagicMock(spec=Path)
        session.physical_data_model.write.yaml(write_yaml)

        assert len(session._store.physical_data_model) == 1
        assert len(session._store.provenance) == 3
        assert isinstance(session._store.state, states.PhysicalState)
        # there is no state change when writing
        assert isinstance(session._store.provenance[-1].source_state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].target_state, states.PhysicalState)
