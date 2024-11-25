from datetime import datetime, timezone

from cognite.neat._rules.models.mapping import load_classic_to_core_mapping
from cognite.neat._rules.transformers import RuleMapper
from cognite.neat._store._provenance import Change

from ._state import SessionState
from .exceptions import session_class_wrapper


@session_class_wrapper
class MappingAPI:
    def __init__(self, state: SessionState):
        self._state = state

    def classic_to_core(self, org_name: str) -> None:
        """Map classic types to core types.

        Note this automatically creates an extended CogniteCore model.

        """
        source_id, rules = self._state.data_model.last_verified_dms_rules

        start = datetime.now(timezone.utc)
        transformer = RuleMapper(load_classic_to_core_mapping(org_name, rules.metadata.space, rules.metadata.version))
        output = transformer.transform(rules)
        end = datetime.now(timezone.utc)

        change = Change.from_rules_activity(
            output,
            transformer.agent,
            start,
            end,
            "Mapping classic to core",
            self._state.data_model.provenance.source_entity(source_id)
            or self._state.data_model.provenance.target_entity(source_id),
        )

        self._state.data_model.write(output.rules, change)
