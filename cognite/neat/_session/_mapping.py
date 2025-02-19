from cognite.neat._issues import IssueList
from cognite.neat._rules.models.mapping import load_classic_to_core_mapping
from cognite.neat._rules.transformers import (
    AsParentPropertyId,
    ChangeViewPrefix,
    IncludeReferenced,
    RuleMapper,
    VerifiedRulesTransformer,
)

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class MappingAPI:
    def __init__(self, state: SessionState):
        self.data_model = DataModelMappingAPI(state)


@session_class_wrapper
class DataModelMappingAPI:
    def __init__(self, state: SessionState):
        self._state = state

    def classic_to_core(self, company_prefix: str | None = None, use_parent_property_name: bool = True) -> IssueList:
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
        if self._state.rule_store.empty:
            raise NeatSessionError("No rules to map")
        last_entity = self._state.rule_store.provenance[-1].target_entity
        if last_entity.dms is None:
            raise NeatSessionError("Data model not converted to DMS. Try running `neat.convert('dms')` first.")
        rules = last_entity.dms
        if self._state.client is None:
            raise NeatSessionError("Client is required to map classic to core")

        transformers: list[VerifiedRulesTransformer] = []
        if company_prefix:
            transformers.append(ChangeViewPrefix("Classic", company_prefix))
        transformers.extend(
            [
                RuleMapper(load_classic_to_core_mapping(company_prefix, rules.metadata.space, rules.metadata.version)),
                IncludeReferenced(self._state.client),
            ]
        )
        if use_parent_property_name:
            transformers.append(AsParentPropertyId(self._state.client))
        return self._state.rule_transform(*transformers)
