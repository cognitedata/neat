from collections import UserList
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, cast

from cognite.neat._client.client import NeatClient
from cognite.neat._config import NeatConfig
from cognite.neat._data_model._shared import OnSuccess, OnSuccessIssuesChecker, OnSuccessResultProducer
from cognite.neat._data_model._snapshot import SchemaSnapshot
from cognite.neat._data_model.deployer.data_classes import DeploymentResult
from cognite.neat._data_model.deployer.deployer import SchemaDeployer
from cognite.neat._data_model.exporters import DMSExporter, DMSFileExporter
from cognite.neat._data_model.exporters._api_exporter import DMSAPIExporter
from cognite.neat._data_model.exporters._table_exporter.exporter import DMSTableExporter
from cognite.neat._data_model.importers import DMSImporter, DMSTableImporter
from cognite.neat._data_model.importers._api_importer import DMSAPIImporter
from cognite.neat._data_model.models.dms import RequestSchema as PhysicalDataModel
from cognite.neat._data_model.models.dms._limits import SchemaLimits
from cognite.neat._exceptions import DataModelImportException
from cognite.neat._issues import IssueList
from cognite.neat._state_machine._states import EmptyState, PhysicalState, State
from cognite.neat._utils.text import NEWLINE

from ._provenance import Change, Provenance

Agents = DMSExporter | DMSTableImporter | DMSImporter


class NeatStore:
    def __init__(self, config: NeatConfig, client: NeatClient) -> None:
        self.physical_data_model = DataModelList()
        self.provenance = Provenance()
        self.state: State = EmptyState()
        self._client = client
        self._config = config

        # Placeholder for CDF schema and limit snapshot
        self._cdf_snapshot: SchemaSnapshot | None = None
        self._cdf_limits: SchemaLimits | None = None

    @property
    def cdf_limits(self) -> SchemaLimits:
        if not self._cdf_limits:
            self._cdf_limits = SchemaLimits.from_api_response(self._client.statistics.project())
        return self._cdf_limits

    @property
    def cdf_snapshot(self) -> SchemaSnapshot:
        if not self._cdf_snapshot:
            self._cdf_snapshot = SchemaSnapshot.fetch_entire_cdf(self._client)
        return self._cdf_snapshot

    def read_physical(self, reader: DMSImporter, on_success: OnSuccess | None = None) -> None:
        """Read object from the store"""
        self._can_agent_do_activity(reader)

        change, data_model = self._do_activity(reader.to_data_model, on_success)

        if data_model:
            change.target_entity = self.physical_data_model.generate_reference(cast(PhysicalDataModel, data_model))
            self.physical_data_model.append(data_model)
            self.state = self.state.transition(reader)
            change.target_state = self.state

        self.provenance.append(change)

    def write_physical(self, writer: DMSExporter, on_success: OnSuccess | None = None, **kwargs: Any) -> None:
        """Write object into the store"""
        self._can_agent_do_activity(writer)

        activity: Callable
        if isinstance(writer, DMSFileExporter):
            activity = writer.export_to_file
            if not kwargs.get("file_path"):
                raise RuntimeError("file_path must be provided when using a DMSFileExporter")
        else:
            activity = writer.export

        data_model = self._gather_data_model(writer)

        change, _ = self._do_activity(activity, on_success, data_model=data_model, **kwargs)

        if not change.issues:
            change.target_entity = "ExternalEntity"
            self.state = self.state.transition(writer)
            change.target_state = self.state

        self.provenance.append(change)

        if (
            isinstance(writer, DMSAPIExporter)
            and isinstance(on_success, SchemaDeployer)
            and not on_success.options.dry_run
        ):
            # Update CDF snapshot after successful deployment
            self._cdf_snapshot = SchemaSnapshot.fetch_entire_cdf(self._client)

    def _gather_data_model(self, writer: DMSExporter) -> PhysicalDataModel:
        """Gather the current physical data model from the store

        Args:
            writer (DMSExporter): The exporter that will be used to write the data model.
        """
        # getting provenance of the last successful physical data model read
        change = self.provenance.last_physical_data_model_read()

        if not change:
            raise RuntimeError("No successful physical data model read found in provenance.")

        # We do not want to modify the data model for API representations
        if not (change.agent == DMSAPIImporter.__name__ and isinstance(writer, DMSTableExporter)):
            return self.physical_data_model[-1]

        # This will handle data model that are partially and require to be converted to
        # tabular representation to include all containers referenced by views.
        copy = self.physical_data_model[-1].model_copy(deep=True)
        container_refs = {container.as_reference() for container in copy.containers}

        for view in copy.views:
            for container in view.used_containers:
                if container not in container_refs and (cdf_container := self.cdf_snapshot.containers.get(container)):
                    copy.containers.append(cdf_container)
                    container_refs.add(container)

        return copy

    def _can_agent_do_activity(self, agent: Agents) -> None:
        """Validate if activity can be performed in the current state and considering provenance"""
        if not self.state.can_transition(agent):
            # specific error messages for common mistakes
            if isinstance(agent, DMSImporter) and isinstance(self.state, PhysicalState):
                raise RuntimeError(
                    "⚠️ Cannot read data model, there is already a data model in the session!"
                    f"{NEWLINE}Start a new session to read a new data model."
                )

            if isinstance(agent, DMSExporter) and isinstance(self.state, EmptyState):
                raise RuntimeError(
                    "⚠️ Cannot write data model, there is no data model in the session!"
                    f"{NEWLINE}Read a data model first!"
                )
            raise RuntimeError(f"Cannot run {type(agent).__name__} in state {self.state}")

        if (
            isinstance(agent, DMSExporter)
            and self.provenance.last_change
            and (error_count := self.provenance.last_change.error_count) > 0
        ):
            raise RuntimeError(
                f"⚠️ Cannot write data model, the model has {error_count} errors!"
                f"{NEWLINE}Resolve issues before exporting the data model."
                f"{NEWLINE}You can inspect issues using neat.issues"
            )

        # need implementation of checking if required predecessor activities have been done
        # this will be done by running self.provenance.can_agent_do_activity(agent)

    def _do_activity(
        self, activity: Callable, on_success: OnSuccess | None = None, **kwargs: Any
    ) -> tuple[Change, PhysicalDataModel | None]:
        """Execute activity and capture timing, results, and issues"""
        start = datetime.now(timezone.utc)
        created_data_model: PhysicalDataModel | None = None
        issues = IssueList()
        errors = IssueList()
        deployment_result: DeploymentResult | None = None

        try:
            created_data_model = activity(**kwargs)
            if created_data_model and on_success:
                on_success.run(created_data_model)
                if isinstance(on_success, OnSuccessIssuesChecker):
                    issues.extend(on_success.issues)
                elif isinstance(on_success, OnSuccessResultProducer):
                    deployment_result = on_success.result
                else:
                    raise RuntimeError(f"Unknown OnSuccess type {type(on_success).__name__}")

        # we catch import exceptions to capture issues and errors in provenance
        except DataModelImportException as e:
            errors.extend(e.errors)

        # these are all other errors, such as missing file, wrong format, etc.
        except Exception as e:
            raise e

        end = datetime.now(timezone.utc)

        return Change(
            start=start,
            end=end,
            source_state=self.state,
            agent=type(activity.__self__).__name__ if hasattr(activity, "__self__") else "UnknownAgent",
            issues=issues,
            errors=errors,
            result=deployment_result,
            activity=Change.standardize_activity_name(activity.__name__, start, end),
        ), created_data_model


class DataModelList(UserList[PhysicalDataModel]):
    def iteration(self, data_model: PhysicalDataModel) -> int:
        """Get iteration number for data model"""
        for i, existing in enumerate(self):
            if existing.data_model == data_model.data_model:
                return i + 2
        return 1

    def generate_reference(self, data_model: PhysicalDataModel) -> str:
        """Generate reference string for data model based on iteration"""
        space = data_model.data_model.space
        external_id = data_model.data_model.external_id
        version = data_model.data_model.version
        iteration = self.iteration(data_model)

        return f"physical/{space}/{external_id}/{version}/{iteration}"

    def get_by_reference(self, reference: str) -> PhysicalDataModel | None:
        """Get data model by reference string"""

        raise NotImplementedError("Not implemented yet")
