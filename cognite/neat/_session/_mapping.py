from datetime import datetime, timezone

from cognite.neat._client import NeatClient
from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._rules.importers import DMSImporter
from cognite.neat._rules.models.dms import DMSValidation
from cognite.neat._rules.models.mapping import load_classic_to_core_mapping
from cognite.neat._rules.transformers import AsParentPropertyId, RuleMapper, VerifyDMSRules
from cognite.neat._store._provenance import Agent as ProvenanceAgent
from cognite.neat._store._provenance import Change

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

        start = datetime.now(timezone.utc)

        source_id, rules = self._state.data_model.last_verified_dms_rules
        view_ids, container_ids = DMSValidation(rules, self._client).imported_views_and_containers_ids()
        if not (view_ids or container_ids):
            print(
                f"Data model {rules.metadata.as_data_model_id()} does not have any referenced views or containers."
                f"that is not already included in the data model."
            )
            return
        if self._client is None:
            raise NeatSessionError(
                "No client provided. You are referencing unknown views and containers in your data model, "
                "NEAT needs a client to lookup the definitions. "
                "Please set the client in the session, NeatSession(client=client)."
            )
        schema = self._client.schema.retrieve([v.as_id() for v in view_ids], [c.as_id() for c in container_ids])
        copy_ = rules.model_copy(deep=True)
        copy_.metadata.version = f"{rules.metadata.version}_completed"
        importer = DMSImporter(schema)
        imported = importer.to_rules()
        if imported.rules is None:
            self._state.data_model.issue_lists.append(imported.issues)
            raise NeatSessionError(
                "Could not import the referenced views and containers. "
                "See `neat.inspect.issues()` for more information."
            )
        verified = VerifyDMSRules("continue", validate=False).transform(imported.rules)
        if verified.rules is None:
            self._state.data_model.issue_lists.append(verified.issues)
            raise NeatSessionError(
                "Could not verify the referenced views and containers. "
                "See `neat.inspect.issues()` for more information."
            )
        if copy_.containers is None:
            copy_.containers = verified.rules.containers
        else:
            existing_containers = {c.container for c in copy_.containers}
            copy_.containers.extend(
                [c for c in verified.rules.containers or [] if c.container not in existing_containers]
            )
        existing_views = {v.view for v in copy_.views}
        copy_.views.extend([v for v in verified.rules.views if v.view not in existing_views])
        end = datetime.now(timezone.utc)

        change = Change.from_rules_activity(
            copy_,
            ProvenanceAgent(id_=DEFAULT_NAMESPACE["agent/"]),
            start,
            end,
            (f"Included referenced views and containers in the data model {rules.metadata.as_data_model_id()}"),
            self._state.data_model.provenance.source_entity(source_id)
            or self._state.data_model.provenance.target_entity(source_id),
        )

        self._state.data_model.write(copy_, change)

        if not use_parent_property_name:
            return

        source_id, rules = self._state.data_model.last_verified_dms_rules
        start = datetime.now(timezone.utc)
        transformer = AsParentPropertyId(self._client)
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
