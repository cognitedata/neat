from pathlib import Path

import pytest

from cognite.neat import _state_machine as states
from cognite.neat._session._session import NeatSession
from tests.tests_unit.test_data_model.test_importers.test_dms_table_importer import valid_dms_yaml_formats

session = NeatSession()


class TestNeatSession:
    def test_read_data_model(self, tmp_path: Path) -> None:
        read_yaml = tmp_path / "read.yaml"
        read_yaml.write_text(next(iter(valid_dms_yaml_formats())).values[0])  # type: ignore [attr-defined]

        session.physical_data_model.read.yaml(read_yaml)
        assert len(session._store.physical_data_model) == 1
        assert len(session._store.provenance) == 1
        assert isinstance(session._store.state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].source_state, states.EmptyState)
        assert isinstance(session._store.provenance[-1].target_state, states.PhysicalState)

    def test_write_data_model(self, tmp_path: Path) -> None:
        write_yaml = tmp_path / "write.yaml"
        session.physical_data_model.write.yaml(write_yaml, exclude_none=False)

        assert len(session._store.physical_data_model) == 1
        assert len(session._store.provenance) == 2
        assert isinstance(session._store.state, states.PhysicalState)
        # there is no state change when writing
        assert isinstance(session._store.provenance[-1].source_state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].target_state, states.PhysicalState)

    def test_forbid_read_in_physical_state(self, tmp_path: Path) -> None:
        read_yaml = tmp_path / "read.yaml"
        read_yaml.write_text("")

        with pytest.raises(RuntimeError) as e:
            session.physical_data_model.read.yaml(read_yaml)

        assert "Cannot run DMSTableImporter in state PhysicalState" in str(e.value)
        assert len(session._store.physical_data_model) == 1

        # no change took place
        assert len(session._store.provenance) == 2

        # we remain in physical state even though we hit Forbidden state, auto-recovery
        assert isinstance(session._store.state, states.PhysicalState)

    def test_write_again_data_model(self, tmp_path: Path) -> None:
        write_yaml = tmp_path / "write.yaml"
        session.physical_data_model.write.yaml(write_yaml, exclude_none=False)

        assert len(session._store.physical_data_model) == 1
        assert len(session._store.provenance) == 3
        assert isinstance(session._store.state, states.PhysicalState)
        # there is no state change when writing
        assert isinstance(session._store.provenance[-1].source_state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].target_state, states.PhysicalState)
