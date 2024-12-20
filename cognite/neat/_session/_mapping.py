from cognite.neat._client import NeatClient
from cognite.neat._issues import IssueList
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.models.mapping import load_classic_to_core_mapping
from cognite.neat._rules.transformers import AsParentPropertyId, IncludeReferenced, RuleMapper

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class MappingAPI:
    def __init__(self, state: SessionState, client: NeatClient | None = None):
        self.data_model = DataModelMappingAPI(state, client)


@session_class_wrapper
class DataModelMappingAPI:
    def __init__(self, state: SessionState, client: NeatClient | None = None):
        self._state = state
        self._client = client

    def classic_to_core(self, company_prefix: str, use_parent_property_name: bool = True) -> IssueList:
        """Map classic types to core types.

        Note this automatically creates an extended CogniteCore model.

        Args:
            company_prefix: Prefix used for all extended CogniteCore types.
            use_parent_property_name: Whether to use the parent property name in the extended CogniteCore model.
                See below for more information.

        If you extend CogniteAsset, with for example, ClassicAsset. You will map the property `parentId` to `parent`.
        If you set `user_parent_property_name` to True, the `parentId` will be renamed to `parent` after the
        mapping is done. If you set it to False, the property will remain `parentId`.

        Example:
            ```python
            neat.mapping.classic_to_core(company_prefix="WindFarmX", use_parent_property_name=True)
            ```
        """
        rules = self._state.rule_store.get_last_successful_entity().result
        if not isinstance(rules, DMSRules):
            # Todo better hint of what you should do.
            raise NeatSessionError(f"Expected DMSRules, got {type(rules)}")

        if self._client is None:
            raise NeatSessionError("Client is required to map classic to core")

        transformers = [
            RuleMapper(load_classic_to_core_mapping(company_prefix, rules.metadata.space, rules.metadata.version)),
            IncludeReferenced(self._client),
        ]
        if use_parent_property_name:
            transformers.append(AsParentPropertyId(self._client))
        return self._state.rule_transform(*transformers)
