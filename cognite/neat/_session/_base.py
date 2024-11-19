from datetime import datetime, timezone
from typing import Literal, cast

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm

from cognite.neat import _version
from cognite.neat._issues import IssueList, catch_issues
from cognite.neat._issues.errors import RegexViolationError
from cognite.neat._rules import importers
from cognite.neat._rules._shared import ReadRules, VerifiedRules
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.models.information._rules_input import InformationInputRules
from cognite.neat._rules.transformers import ConvertToRules, VerifyAnyRules
from cognite.neat._rules.transformers._converters import ConversionTransformer
from cognite.neat._store._provenance import (
    INSTANCES_ENTITY,
    Change,
)
from cognite.neat._utils.auth import _CLIENT_NAME

from ._collector import _COLLECTOR, Collector
from ._inspect import InspectAPI
from ._prepare import PrepareAPI
from ._read import ReadAPI
from ._set import SetAPI
from ._show import ShowAPI
from ._state import SessionState
from ._to import ToAPI
from .engine import load_neat_engine
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class NeatSession:
    def __init__(
        self,
        client: CogniteClient | None = None,
        storage: Literal["memory", "oxigraph"] = "memory",
        verbose: bool = True,
        load_engine: Literal["newest", "cache", "skip"] = "cache",
    ) -> None:
        self._client = client
        self._verbose = verbose
        self._state = SessionState(store_type=storage)
        self.read = ReadAPI(self._state, client, verbose)
        self.to = ToAPI(self._state, client, verbose)
        self.prepare = PrepareAPI(self._state, verbose)
        self.show = ShowAPI(self._state)
        self.set = SetAPI(self._state, verbose)
        self.inspect = InspectAPI(self._state)
        self.opt = OptAPI()
        self.opt._display()
        if self._client is not None and self._client._config is not None:
            self._client._config.client_name = _CLIENT_NAME
        if load_engine != "skip" and (engine_version := load_neat_engine(client, load_engine)):
            print(f"Neat Engine {engine_version} loaded.")

    @property
    def version(self) -> str:
        return _version.__version__

    def verify(self) -> IssueList:
        source_id, last_unverified_rule = self._state.data_model.last_unverified_rule
        transformer = VerifyAnyRules("continue")
        start = datetime.now(timezone.utc)
        output = transformer.try_transform(last_unverified_rule)
        end = datetime.now(timezone.utc)

        if output.rules:
            change = Change.from_rules_activity(
                output.rules,
                transformer.agent,
                start,
                end,
                f"Verified data model {source_id} as {output.rules.metadata.identifier}",
                self._state.data_model.provenance.source_entity(source_id)
                or self._state.data_model.provenance.target_entity(source_id),
            )

            self._state.data_model.write(output.rules, change)

            if isinstance(output.rules, InformationRules):
                self._state.instances.store.add_rules(output.rules)

        output.issues.action = "verify"
        self._state.data_model.issue_lists.append(output.issues)
        if output.issues:
            print("You can inspect the issues with the .inspect.issues(...) method.")
        return output.issues

    def convert(self, target: Literal["dms", "information"]) -> IssueList:
        start = datetime.now(timezone.utc)
        issues = IssueList()
        converter: ConversionTransformer | None = None
        converted_rules: VerifiedRules | None = None
        with catch_issues(issues):
            if target == "dms":
                source_id, info_rules = self._state.data_model.last_verified_information_rules
                converter = ConvertToRules(DMSRules)
                converted_rules = converter.transform(info_rules).rules
            elif target == "information":
                source_id, dms_rules = self._state.data_model.last_verified_dms_rules
                converter = ConvertToRules(InformationRules)
                converted_rules = converter.transform(dms_rules).rules
            else:
                # Session errors are not caught by the catch_issues context manager
                raise NeatSessionError(f"Target {target} not supported.")

        end = datetime.now(timezone.utc)
        if issues:
            self._state.data_model.issue_lists.append(issues)

        if converted_rules is not None and converter is not None:
            # Provenance
            change = Change.from_rules_activity(
                converted_rules,
                converter.agent,
                start,
                end,
                f"Converted data model {source_id} to {converted_rules.metadata.identifier}",
                self._state.data_model.provenance.source_entity(source_id)
                or self._state.data_model.provenance.target_entity(source_id),
            )

            self._state.data_model.write(converted_rules, change)

            if self._verbose and not issues.has_errors:
                print(f"Rules converted to {target}")
        else:
            print("Conversion failed.")
        if issues:
            print("You can inspect the issues with the .inspect.issues(...) method.")
            if issues.has_error_type(RegexViolationError):
                print("You can use .prepare. to try to fix the issues")

        return issues

    def infer(
        self,
        model_id: dm.DataModelId | tuple[str, str, str] = (
            "neat_space",
            "NeatInferredDataModel",
            "v1",
        ),
        max_number_of_instance: int = 100,
    ) -> IssueList:
        """Data model inference from instances.

        Args:
            model_id: The ID of the inferred data model.
            max_number_of_instance: The maximum number of instances to use for inference.
        """
        model_id = dm.DataModelId.load(model_id)

        start = datetime.now(timezone.utc)
        importer = importers.InferenceImporter.from_graph_store(
            store=self._state.instances.store,
            max_number_of_instance=max_number_of_instance,
        )
        inferred_rules: ReadRules = importer.to_rules()
        end = datetime.now(timezone.utc)

        if model_id.space:
            cast(InformationInputRules, inferred_rules.rules).metadata.space = model_id.space
        if model_id.external_id:
            cast(InformationInputRules, inferred_rules.rules).metadata.external_id = model_id.external_id

        if model_id.version:
            cast(InformationInputRules, inferred_rules.rules).metadata.version = model_id.version

        # Provenance
        change = Change.from_rules_activity(
            inferred_rules,
            importer.agent,
            start,
            end,
            "Inferred data model",
            INSTANCES_ENTITY,
        )

        self._state.data_model.write(inferred_rules, change)
        return inferred_rules.issues

    def _repr_html_(self) -> str:
        state = self._state
        if (
            not state.instances.has_store
            and not state.data_model.has_unverified_rules
            and not state.data_model.has_verified_rules
        ):
            return "<strong>Empty session</strong>. Get started by reading something with the <em>.read</em> attribute."

        output = []

        if state.data_model.has_unverified_rules and not state.data_model.has_verified_rules:
            rules: ReadRules = state.data_model.last_unverified_rule[1]
            output.append(f"<H2>Unverified Data Model</H2><br />{rules.rules._repr_html_()}")  # type: ignore

        if state.data_model.has_verified_rules:
            output.append(f"<H2>Verified Data Model</H2><br />{state.data_model.last_verified_rule[1]._repr_html_()}")  # type: ignore

        if state.instances.has_store:
            output.append(f"<H2>Instances</H2> {state.instances.store._repr_html_()}")

        return "<br />".join(output)


@session_class_wrapper
class OptAPI:
    def __init__(self, collector: Collector | None = None) -> None:
        self._collector = collector or _COLLECTOR

    def _display(self) -> None:
        if self._collector.opted_in or self._collector.opted_out:
            return
        print(
            "For Neat to improve, we need to collect usage information. "
            "You acknowledge and agree that neat may collect usage information."
            "To remove this message run 'neat.opt.in_() "
            "or to stop collecting usage information run 'neat.opt.out()'."
        )

    def in_(self) -> None:
        self._collector.enable()
        print("You have successfully opted in to data collection.")

    def out(self) -> None:
        self._collector.disable()
        print("You have successfully opted out of data collection.")
