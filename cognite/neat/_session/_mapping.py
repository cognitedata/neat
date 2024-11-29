from datetime import datetime, timezone

from cognite.neat._client import NeatClient
from cognite.neat._rules.models.mapping import load_classic_to_core_mapping
from cognite.neat._rules.transformers import AsParentName, RuleMapper
from cognite.neat._store._provenance import Change

from ._state import SessionState
from .exceptions import session_class_wrapper


@session_class_wrapper
class MappingAPI:
    def __init__(self, state: SessionState, client: NeatClient | None = None):
        self._state = state
        self._client = client

    def classic_to_core(self, company_prefix: str, use_parent_property_name: bool = True) -> None:
        """Map classic types to core types.

        Note this automatically creates an extended CogniteCore model.

        Args:
            company_prefix: Prefix used for all extended CogniteCore types.
            use_parent_property_name: Whether to use the parent property name in the extended CogniteCore model.
                See below for more information.

        If you extend CogniteAsset, with for example, ClassicAsset. You will map the property `parentId` to `parent`.
        If you set `user_parent_property_name` to True, the `parentId` will be renamed to `parent` after the
        mapping is done. If you set it to False, the property will remain `parentId`.
        """
        source_id, rules = self._state.data_model.last_verified_dms_rules

        start = datetime.now(timezone.utc)
        transformer = RuleMapper(
            load_classic_to_core_mapping(company_prefix, rules.metadata.space, rules.metadata.version)
        )
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
        if not use_parent_property_name:
            return

        start = datetime.now(timezone.utc)
        transformer = AsParentName(self._client)
        output = transformer.transform(rules)
        end = datetime.now(timezone.utc)

        change = Change.from_rules_activity(
            output,
            transformer.agent,
            start,
            end,
            "Renaming property names to parent name",
            self._state.data_model.provenance.source_entity(source_id)
            or self._state.data_model.provenance.target_entity(source_id),
        )

        self._state.data_model.write(output.rules, change)
