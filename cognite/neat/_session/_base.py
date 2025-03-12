from pathlib import Path
from typing import Literal

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm

from cognite.neat import _version
from cognite.neat._client import NeatClient
from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import RegexViolationError
from cognite.neat._issues.errors._general import NeatImportError
from cognite.neat._rules import importers
from cognite.neat._rules.models import DMSRules
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.transformers import (
    InformationToDMS,
    MergeDMSRules,
    MergeInformationRules,
    ToDMSCompliantEntities,
    VerifyInformationRules,
)
from cognite.neat._store._rules_store import RulesEntity
from cognite.neat._utils.auxiliary import local_import

from ._collector import _COLLECTOR, Collector
from ._drop import DropAPI
from ._explore import ExploreAPI
from ._fix import FixAPI
from ._inspect import InspectAPI
from ._mapping import MappingAPI
from ._prepare import PrepareAPI
from ._read import ReadAPI
from ._set import SetAPI
from ._show import ShowAPI
from ._state import SessionState
from ._subset import SubsetAPI
from ._template import TemplateAPI
from ._to import ToAPI
from .engine import load_neat_engine
from .exceptions import session_class_wrapper


@session_class_wrapper
class NeatSession:
    """Creates a new NeatSession.

    This is the main entry point for using Neat. It provides access to the different APIs that can be used to read,
    write, and manipulate data and data models.

    Args:
        client: The CogniteClient to use for reading and writing data.
        storage: The storage type to use for storing data and data models. Can be either "memory" or "oxigraph".
            In "memory" mode works well for small data sets and when only working with data models. It is works
            well for all notebook environments. In "oxigraph" mode, the data is stored in an Oxigraph database. This
            is more performant for larger data sets and when working with data. Note that this option requires
            additional dependencies to be installed and is not available in CDF Notebooks.
        verbose: Whether to print information about the operations being performed.
        load_engine: Whether to load the Neat Engine. Can be "newest", "cache", or "skip". "newest" will always
            check for the newest version of the engine. "cache" will load the engine if it has been downloaded before.
            "skip" will not load the engine.

    Example:
        Instantiate a NeatSession outside CDF jupyter notebook (needs instantiation of a CogniteClient)
        ```python
        from cognite.neat import get_cognite_client
        from cognite.neat import NeatSession

        client = get_cognite_client(env_file_name=".env")
        neat = NeatSession(client)
        ```

    Example:
        Instantiate a NeatSession inside a CDF jupyter notebook (use your user's CogniteClient directly)
        ```python
        from cognite.client import CogniteClient
        from cognite.neat import NeatSession

        client = CogniteClient()
        neat = NeatSession(client)
        ```
    """

    def __init__(
        self,
        client: CogniteClient | None = None,
        storage: Literal["memory", "oxigraph"] | None = None,
        storage_path: str | None = None,
        verbose: bool = True,
        load_engine: Literal["newest", "cache", "skip"] = "cache",
    ) -> None:
        self._verbose = verbose
        self._state = SessionState(
            store_type=storage or self._select_most_performant_store(),
            storage_path=Path(storage_path) if storage_path else None,
            client=NeatClient(client) if client else None,
        )
        self.read = ReadAPI(self._state, verbose)
        self.to = ToAPI(self._state, verbose)
        self.fix = FixAPI(self._state, verbose)
        self.prepare = PrepareAPI(self._state, verbose)
        self.show = ShowAPI(self._state)
        self.set = SetAPI(self._state, verbose)
        self.inspect = InspectAPI(self._state)
        self.mapping = MappingAPI(self._state)
        self.drop = DropAPI(self._state)
        self.subset = SubsetAPI(self._state)
        self.template = TemplateAPI(self._state)
        self._explore = ExploreAPI(self._state)
        self.opt = OptAPI()
        self.opt._display()
        if load_engine != "skip" and (engine_version := load_neat_engine(client, load_engine)):
            print(f"Neat Engine {engine_version} loaded.")

    def _select_most_performant_store(self) -> Literal["memory", "oxigraph"]:
        """Select the most performant store based on the current environment."""

        try:
            local_import("pyoxigraph", "oxi")
            local_import("oxrdflib", "oxi")
            return "oxigraph"
        except NeatImportError:
            return "memory"

    @property
    def version(self) -> str:
        """Get the current version of neat.

        Returns:
            The current version of neat used in the session.

        Example:
            ```python
            neat.version
            ```
        """
        return _version.__version__

    def verify(self) -> IssueList:
        """
        Verify the Data Model schema before the model can be written to CDF. If verification was unsuccessful, use
        `.inspect.issues()` to see what went wrong.

        Example:
            Verify a data model after reading a source file and inferring the data model
            ```python
            # From an active NeatSession
            ...
            neat.read.xml.dexpi("url_or_path_to_dexpi_file")
            neat.infer()
            neat.verify()
            ```
        """
        print("This action has no effect. Neat no longer supports unverified data models.")
        return IssueList()

    def convert(self, reserved_properties: Literal["error", "warning"] = "warning") -> IssueList:
        """Converts the last verified data model to the target type.

        Args:
            reserved_properties: What to do with reserved properties. Can be "error" or "warning".

        Example:
            Convert to DMS rules
            ```python
            neat.convert()
            ```
        """
        self._state._raise_exception_if_condition_not_met(
            "Convert to physical", has_dms_rules=False, has_information_rules=True
        )
        converter = InformationToDMS(reserved_properties=reserved_properties)

        issues = self._state.rule_transform(converter)

        if self._verbose and not issues.has_errors:
            print("Rules converted to dms.")
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
    ) -> IssueList:
        """Data model inference from instances.

        Args:
            model_id: The ID of the inferred data model.

        Example:
            Infer a data model after reading a source file
            ```python
            # From an active NeatSession
            ...
            neat.read.xml.dexpi("url_or_path_to_dexpi_file")
            neat.infer()
            ```
        """
        self._state._raise_exception_if_condition_not_met("Data model inference", instances_required=True)
        return self._infer_subclasses(model_id)

    def _previous_inference(
        self, model_id: dm.DataModelId | tuple[str, str, str], max_number_of_instance: int = 100
    ) -> IssueList:
        # Temporary keeping the old inference method in case we need to revert back
        model_id = dm.DataModelId.load(model_id)
        importer = importers.InferenceImporter.from_graph_store(
            store=self._state.instances.store,
            max_number_of_instance=max_number_of_instance,
            data_model_id=model_id,
        )
        return self._state.rule_import(importer)

    def _infer_subclasses(
        self,
        model_id: dm.DataModelId | tuple[str, str, str] = (
            "neat_space",
            "NeatInferredDataModel",
            "v1",
        ),
    ) -> IssueList:
        """Infer data model from instances."""
        last_entity: RulesEntity | None = None
        if self._state.rule_store.provenance:
            last_entity = self._state.rule_store.provenance[-1].target_entity

        # Note that this importer behaves as a transformer in the rule store when there is an existing rules.
        # We are essentially transforming the last entity's information rules into a new set of information rules.
        importer = importers.SubclassInferenceImporter(
            issue_list=IssueList(),
            graph=self._state.instances.store.graph(),
            rules=last_entity.information if last_entity is not None else None,
            data_model_id=dm.DataModelId.load(model_id) if last_entity is None else None,
        )

        def action() -> tuple[InformationRules, DMSRules | None]:
            unverified_information = importer.to_rules()
            unverified_information = ToDMSCompliantEntities(rename_warning="raise").transform(unverified_information)

            extra_info = VerifyInformationRules().transform(unverified_information)
            if not last_entity:
                return extra_info, None
            merged_info = MergeInformationRules(extra_info).transform(last_entity.information)
            if not last_entity.dms:
                return merged_info, None

            extra_dms = InformationToDMS(reserved_properties="warning").transform(extra_info)

            merged_dms = MergeDMSRules(extra_dms).transform(last_entity.dms)
            return merged_info, merged_dms

        return self._state.rule_store.do_activity(action, importer)

    def _repr_html_(self) -> str:
        state = self._state
        if state.instances.empty and state.rule_store.empty:
            return "<strong>Empty session</strong>. Get started by reading something with the <em>.read</em> attribute."

        output = []

        if state.rule_store.provenance:
            last_entity = state.rule_store.provenance[-1].target_entity
            if last_entity.dms:
                html = last_entity.dms._repr_html_()
            else:
                html = last_entity.information._repr_html_()
            output.append(f"<H2>Data Model</H2><br />{html}")  # type: ignore

        if not state.instances.empty:
            output.append(f"<H2>Instances</H2> {state.instances.store._repr_html_()}")

        return "<br />".join(output)

    def close(self) -> None:
        """Close the session and release resources."""
        self._state.instances.store.dataset.close()

    def __del__(self) -> None:
        """Called by garbage collector"""
        self.close()


@session_class_wrapper
class OptAPI:
    """For the user to decide if they want their usage of neat to be collected or not. We do not collect personal
    information like name etc. only usage.
    """

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
        """Consent to collection of neat user insights."""
        self._collector.enable()
        print("You have successfully opted in to data collection.")

    def out(self) -> None:
        """Opt out of allowing usage of neat to be collected from current user."""
        self._collector.disable()
        print("You have successfully opted out of data collection.")
