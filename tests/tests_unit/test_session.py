import contextlib
import io
from pathlib import Path
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
import respx

from cognite.neat import _state_machine as states
from cognite.neat._client import NeatClientConfig
from cognite.neat._config import NeatConfig
from cognite.neat._data_model.deployer.data_classes import DeploymentResult
from cognite.neat._data_model.importers import DMSAPIImporter, DMSImporter
from cognite.neat._data_model.models.dms import RequestSchema
from cognite.neat._issues import ConsistencyError, IssueList, ModelSyntaxError
from cognite.neat._session._physical import ReadPhysicalDataModel
from cognite.neat._session._session import NeatSession
from cognite.neat._session._usage_analytics._collector import Collector
from cognite.neat._store._provenance import Change
from tests.data import SNAPSHOT_CATALOG
from tests.data.snapshots.utils import update_mock_router


@pytest.fixture()
def new_session(neat_config: NeatClientConfig) -> NeatSession:
    return NeatSession(neat_config)


@pytest.fixture()
def new_session_with_alpha_features(neat_config: NeatClientConfig) -> NeatSession:
    cfg = NeatConfig.create_predefined("legacy-additive")
    cfg.alpha.enable_solution_model_creation = True

    return NeatSession(neat_config, cfg)


@pytest.fixture()
def physical_state_session(new_session: NeatSession, valid_dms_yaml_format: str) -> NeatSession:
    read_yaml = MagicMock(spec=Path)
    read_yaml.read_text.return_value = valid_dms_yaml_format

    new_session.physical_data_model.read.yaml(read_yaml)
    return new_session


@pytest.fixture()
def physical_state_with_consistency_error(
    new_session: NeatSession, consistency_error_dms_yaml_format: str, empty_cdf: respx.MockRouter
) -> NeatSession:
    read_yaml = MagicMock(spec=Path)
    read_yaml.read_text.return_value = consistency_error_dms_yaml_format
    new_session.physical_data_model.read.yaml(read_yaml)
    last_change = new_session._store.provenance.last_change
    assert last_change is not None
    assert last_change.error_count > 0, "The last change should have consistency errors"
    assert isinstance(new_session._store.state, states.PhysicalState)
    return new_session


@pytest.fixture()
def physical_written_session(physical_state_session: NeatSession) -> NeatSession:
    write_yaml = MagicMock(spec=Path)
    physical_state_session.physical_data_model.write.yaml(write_yaml)
    return physical_state_session


@pytest.fixture()
def not_empty_cdf(
    neat_config: NeatClientConfig, example_statistics_response: dict, respx_mock: respx.MockRouter
) -> respx.MockRouter:
    config = neat_config
    # prepare response
    _, cdf_snapshot = SNAPSHOT_CATALOG.load_scenario(
        "ai_readiness", "for_validators", format="snapshots", include_cdm=True
    )

    respx_mock.get(
        config.create_api_url("/models/statistics"),
    ).respond(
        status_code=200,
        json=example_statistics_response,
    )

    # update mock router with snapshot data simulating response from CDF API
    update_mock_router(cdf_snapshot, neat_config, respx_mock)  # type: ignore
    return respx_mock


@pytest.fixture
def session_with_toolkit_schema(new_session: NeatSession, valid_dms_toolkit_yaml_format: str) -> NeatSession:
    read_yaml = MagicMock(spec=Path)
    read_yaml.read_text.return_value = valid_dms_toolkit_yaml_format
    read_yaml.name = "toolkit.yaml"
    read_yaml.suffix = ".yaml"

    new_session.physical_data_model.read.yaml(read_yaml, format="toolkit")
    return new_session


@pytest.fixture
def session_with_neat_partial_schema(new_session: NeatSession, valid_dms_tabular_yaml_partial: str) -> NeatSession:
    read_yaml = MagicMock(spec=Path)
    read_yaml.read_text.return_value = valid_dms_tabular_yaml_partial
    read_yaml.name = "neat.yaml"
    read_yaml.suffix = ".yaml"

    new_session.physical_data_model.read.yaml(read_yaml, format="neat")
    return new_session


@pytest.mark.usefixtures("empty_cdf")
class TestNeatSession:
    def test_error_reading_writing(self, new_session: NeatSession) -> None:
        session = new_session
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            session.physical_data_model.read.yaml("./invalid_path.yaml")

        printed_statements = output.getvalue()
        assert "No such file or directory" in str(printed_statements)
        assert len(session._store.physical_data_model) == 0
        assert len(session._store.provenance) == 0
        assert isinstance(session._store.state, states.EmptyState)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            session.physical_data_model.write.yaml("./invalid_path.yaml")

        printed_statements = output.getvalue()
        assert "⚠️ Cannot write data model, there is no data model in the session" in str(printed_statements)

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
        assert len(cast(IssueList, session._store.provenance[-1].issues)) == 0

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

    def test_write_data_model_to_cdf(self, physical_state_session: NeatSession) -> None:
        session = physical_state_session
        provenance_before = len(session._store.provenance)
        session.physical_data_model.write.cdf(dry_run=True, rollback=True)
        assert len(session._store.provenance) == provenance_before + 1

        assert len(session._store.physical_data_model) == 1
        assert isinstance(session._store.state, states.PhysicalState)
        # there is no state change when writing
        assert isinstance(session._store.provenance[-1].source_state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].target_state, states.PhysicalState)
        assert isinstance(session._store.provenance[-1].result, DeploymentResult)

    def test_forbid_read_in_physical_state(self, physical_state_session: NeatSession) -> None:
        session = physical_state_session
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = ""

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            session.physical_data_model.read.yaml(read_yaml)

        printed_statements = output.getvalue()
        assert "⚠️ Cannot read data model, there is already a data model in the session" in str(printed_statements)
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

    def test_read_dms_from_cdf(self, example_dms_schema_response: dict[str, Any], new_session: NeatSession) -> None:
        session = new_session
        mock_importer = MagicMock(spec=DMSAPIImporter)
        mock_importer.to_data_model.return_value = RequestSchema.model_validate(example_dms_schema_response)
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

    def test_write_data_model_with_consistency_errors(self, physical_state_with_consistency_error: NeatSession) -> None:
        session = physical_state_with_consistency_error

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            session.physical_data_model.write.cdf(dry_run=True)

        printed_statements = output.getvalue()
        assert "⚠️ Cannot write data model, the model has" in str(printed_statements)
        assert "Resolve issues before exporting the data model." in str(printed_statements)

        # no change took place
        assert len(session._store.provenance) == 1, "We should only have the read change from before"

        # we remain in physical state even though we hit Forbidden state, auto-recovery
        assert isinstance(session._store.state, states.PhysicalState)


@pytest.mark.serial
class TestCollector:
    def test_collector_is_singleton(self) -> None:
        collector1 = Collector()
        collector2 = Collector()
        assert collector1 is collector2
        before = collector1.skip_tracking
        change = not before
        collector1.skip_tracking = change
        assert collector2.skip_tracking == change

    def test_get_distinct_id(self) -> None:
        collector = Collector()
        distinct_id1 = collector.get_distinct_id()
        distinct_id2 = collector.get_distinct_id()
        assert distinct_id1 == distinct_id2
        assert isinstance(distinct_id1, str)
        assert len(distinct_id1) > 0

    def test_can_collect(self) -> None:
        collector = Collector()
        assert not collector.can_collect, "We cannot collect when running pytest"


@pytest.mark.usefixtures("empty_cdf")
class TestRender:
    """This tests the HTML rendering methods of various session components.

    They do not check the actual content, just that something is rendered without error.
    """

    def test_render_issues(self, new_session: NeatSession, model_syntax_error_dms_yaml_format: str) -> None:
        session = new_session
        read_yaml = MagicMock(spec=Path)
        read_yaml.read_text.return_value = model_syntax_error_dms_yaml_format
        session.physical_data_model.read.yaml(read_yaml)

        html_repr = session.issues._repr_html_()

        assert isinstance(html_repr, str)

    @pytest.mark.parametrize(
        "dry_run,rollback",
        [
            (True, True),
            (True, False),
            (False, True),
            (False, False),
        ],
    )
    def test_render_results(self, physical_state_session: NeatSession, dry_run: bool, rollback: bool) -> None:
        session = physical_state_session
        session.physical_data_model.write.cdf(dry_run=dry_run, rollback=rollback)

        html_repr = session.result._repr_html_()

        assert isinstance(html_repr, str)

    def test_render_physical_model(self, physical_state_session: NeatSession) -> None:
        session = physical_state_session
        html_repr = session.physical_data_model._repr_html_()

        assert isinstance(html_repr, str)

    def test_render_session_empty(self, new_session: NeatSession) -> None:
        session = new_session
        html_repr = session._repr_html_()

        assert isinstance(html_repr, str)

    def test_render_session_physical(self, physical_state_session: NeatSession) -> None:
        session = physical_state_session
        html_repr = session._repr_html_()

        assert isinstance(html_repr, str)


@pytest.mark.usefixtures("not_empty_cdf")
class TestDMSSerialization:
    def test_toolkit_to_neat_tabular(self, session_with_toolkit_schema: NeatSession) -> None:
        write_yaml = MagicMock(spec=Path)
        session_with_toolkit_schema.physical_data_model.write.yaml(write_yaml, format="neat")

        # missing container from toolkit schema should be added in neat schema
        assert "- Container: cdf_cdm:CogniteDescribable" in write_yaml.write_text.call_args[0][0]

    def test_neat_partial_to_neat_full_tabular(self, session_with_neat_partial_schema: NeatSession) -> None:
        write_yaml = MagicMock(spec=Path)
        session_with_neat_partial_schema.physical_data_model.write.yaml(write_yaml, format="neat")

        # missing container from toolkit schema should be added in neat schema
        assert "- Container: CogniteDescribable" in write_yaml.write_text.call_args[0][0]


@pytest.mark.usefixtures("not_empty_cdf")
class TestDataModelCreation:
    def test_issue_with_view_reference(self, new_session_with_alpha_features: NeatSession) -> None:
        session = new_session_with_alpha_features

        session.physical_data_model.create(  # type: ignore[attr-defined]
            space="cdf_cdm",
            external_id="SolutionModel",
            version="v1",
            views=["cdf=cdm:CogniteAsset(version=v1)", "cdf_cdm:CogniteAsset(version=1320)"],
        )

        last_change = cast(Change, session._store.provenance.last_change)

        by_type = cast(IssueList, last_change.errors).by_type()

        assert len(by_type[ModelSyntaxError]) == 1
        assert "Invalid view reference" in by_type[ModelSyntaxError][0].message

        assert len(by_type[ConsistencyError]) == 1
        assert (
            "'cdf_cdm:CogniteAsset(version=1320)' not found in the provided CDF snapshot"
            in by_type[ConsistencyError][0].message
        )
