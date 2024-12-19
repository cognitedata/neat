from typing import Literal

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm

from cognite.neat import _version
from cognite.neat._client import NeatClient
from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import RegexViolationError
from cognite.neat._rules import importers
from cognite.neat._rules.models._base_input import InputRules
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._rules.transformers import ConvertToRules, InformationToDMS, VerifyAnyRules
from cognite.neat._rules.transformers._converters import ConversionTransformer

from ._collector import _COLLECTOR, Collector
from ._drop import DropAPI
from ._inspect import InspectAPI
from ._mapping import MappingAPI
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
        storage: Literal["memory", "oxigraph"] = "memory",
        verbose: bool = True,
        load_engine: Literal["newest", "cache", "skip"] = "cache",
    ) -> None:
        self._client = NeatClient(client) if client else None
        self._verbose = verbose
        self._state = SessionState(store_type=storage)
        self.read = ReadAPI(self._state, self._client, verbose)
        self.to = ToAPI(self._state, self._client, verbose)
        self.prepare = PrepareAPI(self._client, self._state, verbose)
        self.show = ShowAPI(self._state)
        self.set = SetAPI(self._state, verbose)
        self.inspect = InspectAPI(self._state)
        self.mapping = MappingAPI(self._state, self._client)
        self.drop = DropAPI(self._state)
        self.opt = OptAPI()
        self.opt._display()
        if load_engine != "skip" and (engine_version := load_neat_engine(client, load_engine)):
            print(f"Neat Engine {engine_version} loaded.")

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
        transformer = VerifyAnyRules(validate=True, client=self._client)  # type: ignore[var-annotated]
        issues = self._state.rule_transform(transformer)
        if not issues.has_errors:
            rules = self._state.rule_store.last_verified_rule
            if isinstance(rules, InformationRules):
                self._state.instances.store.add_rules(rules)

        if issues:
            print("You can inspect the issues with the .inspect.issues(...) method.")
        return issues

    def convert(
        self, target: Literal["dms", "information"], mode: Literal["edge_properties"] | None = None
    ) -> IssueList:
        """Converts the last verified data model to the target type.

        Args:
            target: The target type to convert the data model to.
            mode: If the target is "dms", the mode to use for the conversion. None is used for default conversion.
                "edge_properties" treas classes that implements Edge as edge properties.

        Example:
            Convert to DMS rules
            ```python
            neat.convert(target="dms")
            ```

        Example:
            Convert to Information rules
            ```python
            neat.convert(target="information")
            ```
        """
        converter: ConversionTransformer
        if target == "dms":
            converter = InformationToDMS(mode=mode)
        elif target == "information":
            converter = ConvertToRules(InformationRules)
        else:
            raise NeatSessionError(f"Target {target} not supported.")
        issues = self._state.rule_transform(converter)

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

        Example:
            Infer a data model after reading a source file
            ```python
            # From an active NeatSession
            ...
            neat.read.xml.dexpi("url_or_path_to_dexpi_file")
            neat.infer()
            ```
        """
        model_id = dm.DataModelId.load(model_id)
        importer = importers.InferenceImporter.from_graph_store(
            store=self._state.instances.store,
            max_number_of_instance=max_number_of_instance,
            data_model_id=model_id,
        )
        return self._state.rule_import(importer)

    def _repr_html_(self) -> str:
        state = self._state
        if (
            not state.instances.has_store
            and not state.rule_store.has_unverified_rules
            and not state.rule_store.has_verified_rules
        ):
            return "<strong>Empty session</strong>. Get started by reading something with the <em>.read</em> attribute."

        output = []

        if state.rule_store.has_unverified_rules and not state.rule_store.has_verified_rules:
            rules: InputRules = state.rule_store.last_unverified_rule
            output.append(f"<H2>Unverified Data Model</H2><br />{rules._repr_html_()}")  # type: ignore

        if state.rule_store.has_verified_rules:
            output.append(f"<H2>Verified Data Model</H2><br />{state.rule_store.last_verified_rule._repr_html_()}")  # type: ignore

        if state.instances.has_store:
            output.append(f"<H2>Instances</H2> {state.instances.store._repr_html_()}")

        return "<br />".join(output)


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
