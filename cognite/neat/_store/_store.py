from collections import UserList
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, cast

from cognite.neat._data_model._shared import OnSuccess, OnSuccessIssuesChecker, OnSuccessResultProducer
from cognite.neat._data_model.deployer.data_classes import DeploymentResult
from cognite.neat._data_model.exporters import DMSExporter, DMSFileExporter
from cognite.neat._data_model.importers import DMSImporter, DMSTableImporter
from cognite.neat._data_model.models.dms import RequestSchema as PhysicalDataModel
from cognite.neat._exceptions import DataModelImportException
from cognite.neat._issues import IssueList
from cognite.neat._state_machine._states import EmptyState, State

from ._provenance import Change, Provenance

Agents = DMSExporter | DMSTableImporter | DMSImporter


class NeatStore:
    def __init__(self) -> None:
        self.physical_data_model = DataModelList()
        self.provenance = Provenance()
        self.state: State = EmptyState()

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

        change, _ = self._do_activity(activity, on_success, data_model=self.physical_data_model[-1], **kwargs)

        if not change.issues:
            change.target_entity = "ExternalEntity"
            self.state = self.state.transition(writer)
            change.target_state = self.state

        self.provenance.append(change)

    def _can_agent_do_activity(self, agent: Agents) -> None:
        """Validate if activity can be performed in the current state and considering provenance"""
        if not self.state.can_transition(agent):
            raise RuntimeError(f"Cannot run {type(agent).__name__} in state {self.state}")

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
