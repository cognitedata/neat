from collections import UserList
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, cast

from cognite.neat._data_model.exporters import DMSTableExporter
from cognite.neat._data_model.importers import DMSTableImporter
from cognite.neat._data_model.models.dms import RequestSchema as PhysicalDataModel
from cognite.neat._state_machine._states import EmptyState, State

from ._provenance import Change, Provenance

Agents = DMSTableExporter | DMSTableImporter


class NeatStore:
    def __init__(self) -> None:
        self.physical_data_model = DataModelList()
        self.provenance = Provenance()
        self.state: State = EmptyState()

    def read_physical(self, reader: DMSTableImporter) -> None:
        """Read object from the store"""
        self._can_agent_do_activity(reader)

        change, data_model = self._do_activity(reader.to_data_model)

        if data_model:
            change.target_entity = self.physical_data_model.generate_reference(cast(PhysicalDataModel, data_model))
            self.physical_data_model.append(data_model)
            self.state = self.state.transition(reader)
            change.target_state = self.state

        self.provenance.append(change)

    def write_physical(self, writer: DMSTableExporter, **kwargs: Any) -> None:
        """Write object into the store"""
        self._can_agent_do_activity(writer)

        change, _ = self._do_activity(writer.as_yaml, data_model=self.physical_data_model[-1], **kwargs)

        if not change.issues:
            change.target_entity = "ExternalEntity"
            self.state = self.state.transition(writer)
            change.target_state = self.state

        self.provenance.append(change)

    def _can_agent_do_activity(self, agent: Agents) -> None:
        """Validate if activity can be performed in the current state and considering provenance"""
        if not self.state.can_transition(agent):
            raise RuntimeError(f"Cannot run {type(agent).__name__} in state {self.state}")

        if not self.provenance.can_agent_do_activity(agent):
            raise RuntimeError(f"Agent {type(agent).__name__} cannot do activity because...")

    def _do_activity(self, activity: Callable, **kwargs: Any) -> tuple[Change, PhysicalDataModel | None]:
        """Execute activity and capture timing, results, and issues"""
        start = datetime.now(timezone.utc)
        result: PhysicalDataModel | None = None
        issues: list[str] = []

        try:
            result = activity(**kwargs)
        except Exception as e:
            issues.append(str(e))

        end = datetime.now(timezone.utc)

        return Change(
            start=start,
            end=end,
            source_state=self.state,
            agent=type(activity.__self__).__name__ if hasattr(activity, "__self__") else "UnknownAgent",
            issues=issues,
            activity=Change.standardize_activity_name(activity.__name__, start, end),
        ), result


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
