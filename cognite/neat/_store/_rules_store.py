import hashlib
from collections import defaultdict
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Any, cast

import rdflib
from cognite.client import data_modeling as dm
from rdflib import URIRef

from cognite.neat._client import NeatClient
from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._graph.extractors import DMSGraphExtractor, KnowledgeGraphExtractor
from cognite.neat._issues import IssueList, catch_issues
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules._shared import ReadRules, Rules, T_VerifiedRules, VerifiedRules
from cognite.neat._rules.exporters import BaseExporter
from cognite.neat._rules.exporters._base import CDFExporter, T_Export
from cognite.neat._rules.importers import BaseImporter
from cognite.neat._rules.models import DMSRules, InformationRules
from cognite.neat._rules.models._base_input import InputRules
from cognite.neat._rules.transformers import VerifiedRulesTransformer
from cognite.neat._utils.upload import UploadResultList
from cognite.neat._rules.transformers import DMSToInformation, InformationToDMS, MergeInformationRules, MergeDMSRules, VerifyAnyRules

from ._provenance import EMPTY_ENTITY, UNKNOWN_AGENT, Activity, Agent, Change, Entity, Provenance
from .exceptions import EmptyStore, InvalidInputOperation, ActivityFailed, InvalidActivityOutput

@dataclass(frozen=True)
class RulesEntity(Entity):
    information: InformationRules
    dms: DMSRules | None = None

    @property
    def has_dms(self) -> bool:
        return self.dms is not None

@dataclass(frozen=True)
class OutcomeEntity(Entity):
    result: UploadResultList | Path | str | URIRef


class NeatRulesStore:
    def __init__(self) -> None:
        self.provenance = Provenance[RulesEntity]()
        self.exports_by_source_entity_id: dict[rdflib.URIRef, list[Change[OutcomeEntity]]] = defaultdict(list)
        self._last_outcome: UploadResultList | None = None
        self._iteration_by_id: dict[Hashable, int] = {}

    def calculate_provenance_hash(self, shorten: bool = True) -> str:
        sha256_hash = hashlib.sha256()
        for change in self.provenance:
            for id_ in [change.agent.id_, change.activity.id_, change.target_entity.id_, change.source_entity.id_]:
                sha256_hash.update(str(id_).encode("utf-8"))
        calculated_hash = sha256_hash.hexdigest()
        if shorten:
            return calculated_hash[:8]
        return calculated_hash

    def import_(self, importer: BaseImporter, validate: bool = True, client: NeatClient | None = None) -> IssueList:
        if self.provenance:
            raise NeatValueError(f"Data model already exists in the store. Cannot import {importer.source_uri}.")
        source_entity = Entity.create_with_defaults(
            was_attributed_to=UNKNOWN_AGENT,
            id_=importer.source_uri,
        )
        start = datetime.now(timezone.utc)
        verified: InformationRules | DMSRules | None = None
        with catch_issues() as issue_list:
            read_rules = importer.to_rules()
            verified = VerifyAnyRules(validate, client).transform(read_rules)

        end = datetime.now(timezone.utc)
        agent = importer.agent
        activity = Activity(
            was_associated_with=agent,
            ended_at_time=end,
            started_at_time=start,
            used=source_entity,
        )
        if verified is None:
            raise ActivityFailed(activity, issue_list)

        dms: DMSRules | None = None
        if isinstance(verified, InformationRules):
            info = verified
        elif isinstance(verified, DMSRules):
            dms = verified
            info = DMSToInformation().transform(dms)
        else:
            raise InvalidActivityOutput(activity, type(verified))

        target_entity = RulesEntity(
            was_attributed_to=agent,
            was_generated_by=activity,
            information=info,
            dms=dms,
            issues=issue_list,
            # here id can be bumped in case id already exists
            id_=self._create_id(verified),
        )
        change = Change(
            agent=agent,
            activity=activity,
            target_entity=target_entity,
            description=importer.description,
            source_entity=source_entity,
        )
        self.provenance.append(change)
        return issue_list

    def import_graph(self, extractor: KnowledgeGraphExtractor) -> IssueList:
        agent = extractor.agent
        source_entity = Entity.create_with_defaults(
            was_attributed_to=UNKNOWN_AGENT,
            id_=extractor.source_uri,
        )
        _, issues = self._do_activity(extractor.get_information_rules, agent, source_entity, extractor.description)
        if isinstance(extractor, DMSGraphExtractor):
            _, dms_issues = self._do_activity(extractor.get_dms_rules, agent, source_entity, extractor.description)
            issues.extend(dms_issues)
        return issues

    def transform(self, *transformer: VerifiedRulesTransformer) -> IssueList:
        if not self.provenance:
            raise EmptyStore()

        all_issues = IssueList()
        for item in transformer:
            last_change = self.provenance[-1]
            source_entity = last_change.target_entity

            transformer_input = self._get_transformer_input(source_entity, item)
            start = datetime.now(timezone.utc)
            result: InformationRules | DMSRules | None = None
            with catch_issues() as issue_list:
                result = item.transform(transformer_input)
            all_issues.extend(issue_list)
            if result is None:
                return all_issues
            end = datetime.now(timezone.utc)

            activity = Activity(
                was_associated_with=item.agent,
                ended_at_time=end,
                started_at_time=start,
                used=source_entity,
            )
            if isinstance(result, InformationRules):
                info = result
                dms = None
            elif isinstance(result, DMSRules):
                dms = result
                info = source_entity.information
            else:
                raise InvalidActivityOutput(activity, type(result))

            target_entity = RulesEntity(
                was_attributed_to=item.agent,
                was_generated_by=activity,
                information=info,
                dms=dms,
                issues=issue_list,
                # here id can be bumped in case id already exists
                id_=self._create_id(result),
            )
            change = Change(
                agent=item.agent,
                activity=activity,
                target_entity=target_entity,
                description=item.description,
                source_entity=source_entity,
            )
            self.provenance.append(change)
        return all_issues

    @staticmethod
    def _get_transformer_input(source_entity: RulesEntity, transformer: VerifiedRulesTransformer) -> InformationRules | DMSRules:
        # Case 1: We only have information rules
        if source_entity.dms is None:
            if transformer.is_valid_input(source_entity.information):
                return source_entity.information
            raise InvalidInputOperation(expected=(DMSRules, ), have=(InformationRules,))
        # Case 2: We have both information and dms rules and the transformer is compatible with dms rules
        elif isinstance(source_entity.dms, DMSRules) and transformer.is_valid_input(source_entity.dms):
            return source_entity.dms
        # Case 3: We have both information and dms rules and the transformer is compatible with information rules
        raise NeatValueError(f"Cannot do action {transformer.description} on a converted physical model.")

    def export(self, exporter: BaseExporter[T_VerifiedRules, T_Export]) -> T_Export:
        if self.empty:
            raise EmptyStore()
        last_change = self.provenance[-1]
        source_entity = last_change.target_entity
        expected_types = exporter.source_types()

        if source_entity.dms is not None and isinstance(source_entity.dms, expected_types):
            input_ = source_entity.dms
        elif isinstance(source_entity.information, expected_types):
            input_ = source_entity.information
        else:
            available = [InformationRules]
            if source_entity.dms is not None:
                available.append(DMSRules)
            raise InvalidInputOperation(expected=expected_types, have=tuple(available))

        agent = exporter.agent
        start = datetime.now(timezone.utc)
        with catch_issues() as issue_list:
            # Validate the type of the result
            result = exporter.export(input_)
        end = datetime.now(timezone.utc)
        target_id = DEFAULT_NAMESPACE["export-result"]
        activity = Activity(
            was_associated_with=agent,
            ended_at_time=end,
            started_at_time=start,
            used=source_entity,
        )
        target_entity = OutcomeEntity(
            was_attributed_to=agent,
            was_generated_by=activity,
            result=type(result).__name__,
            issues=issue_list,
            id_=target_id,
        )
        change = Change(
            agent=agent,
            activity=activity,
            target_entity=target_entity,
            description=exporter.description,
            source_entity=source_entity,
        )
        self.exports_by_source_entity_id[source_entity.id_].append(change)
        return result

    def export_to_file(self, exporter: BaseExporter, path: Path) -> None:
        last_change = self.provenance[-1]
        source_entity = last_change.target_entity
        if not isinstance(source_entity, ModelEntity):
            # Todo: Provenance should be of an entity type
            raise ValueError("Bug in neat: The last entity in the provenance is not a model entity.")
        expected_types = exporter.source_types()
        if not any(isinstance(source_entity.result, type_) for type_ in expected_types):
            raise InvalidInputOperation(expected=expected_types, got=type(source_entity.result))
        target_id = DEFAULT_NAMESPACE[path.name]
        agent = exporter.agent
        start = datetime.now(timezone.utc)
        with catch_issues() as issue_list:
            exporter.export_to_file(source_entity.result, path)
        end = datetime.now(timezone.utc)

        activity = Activity(
            was_associated_with=agent,
            ended_at_time=end,
            started_at_time=start,
            used=source_entity,
        )
        target_entity = OutcomeEntity(
            was_attributed_to=agent,
            was_generated_by=activity,
            result=path,
            issues=issue_list,
            id_=target_id,
        )
        change = Change(
            agent=agent,
            activity=activity,
            target_entity=target_entity,
            description=exporter.description,
            source_entity=source_entity,
        )
        self.exports_by_source_entity_id[source_entity.id_].append(change)

    def export_to_cdf(self, exporter: CDFExporter, client: NeatClient, dry_run: bool) -> UploadResultList:
        last_change = self.provenance[-1]
        source_entity = last_change.target_entity
        if not isinstance(source_entity, ModelEntity):
            # Todo: Provenance should be of an entity type
            raise ValueError("Bug in neat: The last entity in the provenance is not a model entity.")
        expected_types = exporter.source_types()
        if not any(isinstance(source_entity.result, type_) for type_ in expected_types):
            raise InvalidInputOperation(expected=expected_types, got=type(source_entity.result))

        agent = exporter.agent
        start = datetime.now(timezone.utc)
        target_id = DEFAULT_NAMESPACE["upload-result"]
        result: UploadResultList | None = None
        with catch_issues() as issue_list:
            result = exporter.export_to_cdf(source_entity.result, client, dry_run)
        end = datetime.now(timezone.utc)

        activity = Activity(
            was_associated_with=agent,
            ended_at_time=end,
            started_at_time=start,
            used=source_entity,
        )
        target_entity = OutcomeEntity(
            was_attributed_to=agent,
            was_generated_by=activity,
            result=result,
            issues=issue_list,
            id_=target_id,
        )
        change = Change(
            agent=agent,
            activity=activity,
            target_entity=target_entity,
            description=exporter.description,
            source_entity=source_entity,
        )
        self.exports_by_source_entity_id[source_entity.id_].append(change)
        self._last_outcome = result
        return result

    def _update_source_entity(self, source_entity: Entity, result: Rules, issue_list: IssueList) -> Entity:
        """Update source entity to keep the unbroken provenance chain of changes."""

        # Case 1: Store not empty, source of imported rules is not known
        if not (source_id := self._get_source_id(result)):
            raise NeatValueError(
                "The data model to be read to the current NEAT session"
                " has no relation to the session content."
                " Import will be skipped."
                "\n\nSuggestions:\n\t(1) Start a new NEAT session and "
                "import the data model there."
            )

        # We are taking target entity as it is the entity that produce rules
        # which were updated by activities outside of the rules tore
        update_source_entity: Entity | None = self.provenance.target_entity(source_id)

        # Case 2: source of imported rules not in rules_store
        if not update_source_entity:
            raise NeatValueError(
                "The source of the data model being imported is not in"
                " the content of this NEAT session."
                " Import will be skipped."
                "\n\nSuggestions:"
                "\n\t(1) Start a new NEAT session and import the data model source"
                "\n\t(2) Then import the data model itself"
            )

        # Case 3: source_entity in rules_store and but it is not the latest entity
        if self.provenance[-1].target_entity.id_ != update_source_entity.id_:
            raise NeatValueError(
                "Source of imported data model is not the latest entity in the data model provenance."
                "Pruning required to set the source entity to the latest entity in the provenance."
            )

        # Case 4: source_entity in rules_store and it is not the latest target entity
        if self.provenance[-1].target_entity.id_ != update_source_entity.id_:
            raise NeatValueError(
                "Source of imported rules is not the latest entity in the provenance."
                "Pruning required to set the source entity to the latest entity in the provenance."
            )

        # Case 5: source_entity in rules_store and it is the latest entity
        # Here we need to check if the source and target entities are identical
        # if they are ... we should raise an error and skip importing
        # for now we will just return the source entity that we managed to extract

        return update_source_entity or source_entity

    def _do_activity(
        self, action: Callable[[], Rules | None], agent: Agent, source_entity: Entity, description: str
    ) -> tuple[Any, IssueList]:
        start = datetime.now(timezone.utc)
        result: Rules | None = None
        with catch_issues() as issue_list:
            result = action()
        end = datetime.now(timezone.utc)

        # This handles import activity that needs to be properly registered
        # hence we check if class of action is subclass of BaseImporter
        # and only if the store is not empty !
        if (
            hasattr(action, "__self__")
            and issubclass(action.__self__.__class__, BaseImporter)
            and source_entity.was_attributed_to == UNKNOWN_AGENT
            and result
            and not self.empty
        ):
            source_entity = self._update_source_entity(source_entity, result, issue_list)

        activity = Activity(
            was_associated_with=agent,
            ended_at_time=end,
            started_at_time=start,
            used=source_entity,
        )
        target_entity = ModelEntity(
            was_attributed_to=agent,
            was_generated_by=activity,
            result=result,
            issues=issue_list,
            # here id can be bumped in case id already exists
            id_=self._create_id(result),
        )
        change = Change(
            agent=agent,
            activity=activity,
            target_entity=target_entity,
            description=description,
            source_entity=source_entity,
        )

        self.provenance.append(change)
        return result, issue_list

    def _get_source_id(self, result: Rules) -> rdflib.URIRef | None:
        """Return the source of the result."""

        if isinstance(result, ReadRules) and result.rules is not None and result.rules.metadata.source_id:
            return rdflib.URIRef(result.rules.metadata.source_id)
        if isinstance(result, VerifiedRules):
            return result.metadata.source_id
        return None

    def _get_data_model_id(self, result: Rules) -> dm.DataModelId | None:
        """Return the source of the result."""

        if isinstance(result, ReadRules) and result.rules is not None:
            return result.rules.metadata.as_data_model_id()
        if isinstance(result, VerifiedRules):
            return result.metadata.as_data_model_id()
        return None

    def _create_id(self, result: InformationRules | DMSRules) -> rdflib.URIRef:
        identifier = result.metadata.identifier

        # Here we check if the identifier is already in the iteration dictionary
        # to track specific changes to the same entity, if it is we increment the iteration
        if identifier not in self._iteration_by_id:
            self._iteration_by_id[identifier] = 1
            return identifier

        # If the identifier is already in the iteration dictionary we increment the iteration
        # and update identifier to include the iteration number
        self._iteration_by_id[identifier] += 1
        return identifier + f"/Iteration_{self._iteration_by_id[identifier]}"

    # @property
    # def last_verified_dms_rules(self) -> DMSRules:
    #     for change in reversed(self.provenance):
    #         if isinstance(change.target_entity, ModelEntity) and isinstance(change.target_entity.result, DMSRules):
    #             return change.target_entity.result
    #     raise NeatValueError("No verified DMS rules found in the provenance.")
    #
    # @property
    # def last_verified_information_rules(self) -> InformationRules:
    #     for change in reversed(self.provenance):
    #         if isinstance(change.target_entity, ModelEntity) and isinstance(
    #             change.target_entity.result, InformationRules
    #         ):
    #             return change.target_entity.result
    #     raise NeatValueError("No verified information rules found in the provenance.")

    # @property
    # def last_issues(self) -> IssueList:
    #     if not self.provenance:
    #         raise NeatValueError("No issues found in the provenance.")
    #     last_change = self.provenance[-1]
    #     if last_change.target_entity.issues:
    #         return last_change.target_entity.issues
    #     return last_change.source_entity.issues

    @property
    def last_outcome(self) -> UploadResultList:
        if self._last_outcome is not None:
            return self._last_outcome
        raise NeatValueError("No outcome found in the provenance.")

    @property
    def empty(self) -> bool:
        """Check if the store is empty."""
        return not self.provenance
