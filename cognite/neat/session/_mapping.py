from collections.abc import Hashable

from cognite.neat.core._data_model.models.mapping import load_classic_to_core_mapping
from cognite.neat.core._data_model.transformers import (
    AsParentPropertyId,
    ChangeViewPrefix,
    IncludeReferenced,
    PhysicalDataModelMapper,
    VerifiedDataModelTransformer,
)
from cognite.neat.core._instances.transformers import ConnectionToLiteral, ObjectMapper
from cognite.neat.core._issues import IssueList

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class MappingAPI:
    def __init__(self, state: SessionState):
        self.data_model = DataModelMappingAPI(state)
        self.instances = InstanceMappingAPI(state)


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
        if last_entity.physical is None:
            raise NeatSessionError("Data model not converted to DMS. Try running `neat.convert('dms')` first.")
        rules = last_entity.physical
        if self._state.client is None:
            raise NeatSessionError("Client is required to map classic to core")

        transformers: list[VerifiedDataModelTransformer] = []
        if company_prefix:
            transformers.append(ChangeViewPrefix("Classic", company_prefix))

        transformers.extend(
            [
                PhysicalDataModelMapper(
                    load_classic_to_core_mapping(company_prefix, rules.metadata.space, rules.metadata.version)
                ),
                IncludeReferenced(self._state.client),
            ]
        )
        if use_parent_property_name:
            transformers.append(AsParentPropertyId(self._state.client))
        issues = self._state.rule_transform(*transformers)

        # Convert the labels to literals - note that the mapping changes labels to tags.
        label_predicate = self._state.instances.store.queries.select.property_uri("labels")[0]
        issues.extend(self._state.instances.store.transform(ConnectionToLiteral(None, label_predicate)))
        return issues


@session_class_wrapper
class InstanceMappingAPI:
    def __init__(self, state: SessionState):
        self._state = state

    def value_mapping(self, mapping: dict[Hashable, object], property: str, type: str | None = None) -> IssueList:
        """Maps all values for a given property and type.

        Args:
            mapping: A dictionary where the key is the value to be mapped and the value is the new value.
            property: The property to be mapped.
            type: The type of the instance. If None, all instances with the given property will be mapped.

        Example:
            ```python
            neat.mapping.value_mapping(mapping={"old_value": "new_value"}, property="type", type="Event")
            ```
        """
        self._state._raise_exception_if_condition_not_met("Mapping instance values", instances_required=True)
        predicates = self._state.instances.store.queries.select.property_uri(property)

        if not predicates:
            raise NeatSessionError(f"Property {property} not found in the store.")
        elif len(predicates) > 1:
            raise NeatSessionError(f"Multiple properties found: {predicates}. Please specify the property.")
        predicate = predicates[0]
        if type is not None:
            types_by_uri = self._state.instances.store.queries.select.types()
            type_uris_by_value = {v: k for k, v in types_by_uri.items()}
            if type not in type_uris_by_value:
                raise NeatSessionError(f"Type {type} not found in the store.")
            rdf_type = type_uris_by_value[type]
        else:
            rdf_type = None

        mapper = ObjectMapper(mapping, predicate, rdf_type)

        return self._state.instances.store.transform(mapper)
