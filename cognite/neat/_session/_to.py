from pathlib import Path
from typing import Any, Literal, overload

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import SpaceApply

from cognite.neat._graph import loaders
from cognite.neat._issues import IssueList, catch_warnings
from cognite.neat._rules import exporters
from cognite.neat._rules._constants import PATTERNS
from cognite.neat._rules._shared import VerifiedRules
from cognite.neat._utils.upload import UploadResultCore, UploadResultList

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class ToAPI:
    def __init__(self, state: SessionState, client: CogniteClient | None, verbose: bool) -> None:
        self._state = state
        self._verbose = verbose
        self.cdf = CDFToAPI(state, client, verbose)

    def excel(
        self,
        io: Any,
        model: Literal["dms", "information", "logical", "physical"] | None,
    ) -> None:
        """Export the verified data model to Excel.

        Args:
            io: The file path or file-like object to write the Excel file to.
            model: The format of the data model to export. Defaults to None.
        """
        exporter = exporters.ExcelExporter()
        rules: VerifiedRules
        if model == "information" or model == "logical":
            rules = self._state.data_model.last_verified_information_rules[1]
        elif model == "dms" or model == "physical":
            rules = self._state.data_model.last_verified_dms_rules[1]
        else:
            rules = self._state.data_model.last_verified_rule[1]

        exporter.export_to_file(rules, Path(io))
        return None

    @overload
    def yaml(self, io: None, format: Literal["neat"] = "neat") -> str: ...

    @overload
    def yaml(self, io: Any, format: Literal["neat", "toolkit"] = "neat") -> None: ...

    def yaml(self, io: Any | None = None, format: Literal["neat", "toolkit"] = "neat") -> str | None:
        if format == "neat":
            exporter = exporters.YAMLExporter()
            last_verified = self._state.data_model.last_verified_rule[1]
            if io is None:
                return exporter.export(last_verified)

            exporter.export_to_file(last_verified, Path(io))
        elif format == "toolkit":
            if io is None or not isinstance(io, str | Path):
                raise NeatSessionError(
                    "Please provide a zip file or directory path to write the YAML files to."
                    "This is required for the 'toolkit' format."
                )
            dms_rule = self._state.data_model.last_verified_dms_rules[1]
            exporters.DMSExporter().export_to_file(dms_rule, Path(io))
        else:
            raise NeatSessionError("Please provide a valid format. {['neat', 'toolkit']}")

        return None


@session_class_wrapper
class CDFToAPI:
    def __init__(self, state: SessionState, client: CogniteClient | None, verbose: bool) -> None:
        self._client = client
        self._state = state
        self._verbose = verbose

    def instances(self, space: str | None = None) -> UploadResultList:
        if not self._client:
            raise NeatSessionError("No CDF client provided!")

        space = space or f"{self._state.data_model.last_verified_dms_rules[1].metadata.space}_instances"

        if space and space == self._state.data_model.last_verified_dms_rules[1].metadata.space:
            raise NeatSessionError("Space for instances must be different from the data model space.")
        elif not PATTERNS.space_compliance.match(str(space)):
            raise NeatSessionError("Please provide a valid space name. {PATTERNS.space_compliance.pattern}")

        if not self._client.data_modeling.spaces.retrieve(space):
            self._client.data_modeling.spaces.apply(SpaceApply(space=space))

        loader = loaders.DMSLoader.from_rules(
            self._state.data_model.last_verified_dms_rules[1],
            self._state.instances.store,
            instance_space=space,
        )
        result = loader.load_into_cdf(self._client)
        self._state.instances.outcome.append(result)
        print("You can inspect the details with the .inspect.outcome.instances(...) method.")
        return result

    def data_model(
        self,
        existing_handling: Literal["fail", "skip", "update", "force"] = "skip",
        dry_run: bool = False,
        fallback_one_by_one: bool = False,
    ):
        """Export the verified DMS data model to CDF.

        Args:
            existing_handling: How to handle if component of data model exists. Defaults to "skip".
            dry_run: If True, no changes will be made to CDF. Defaults to False.
            fallback_one_by_one: If True, will fall back to one-by-one upload if batch upload fails. Defaults to False.

        ... note::

        - "fail": If any component already exists, the export will fail.
        - "skip": If any component already exists, it will be skipped.
        - "update": If any component already exists, it will be updated.
        - "force": If any component already exists, it will be deleted and recreated.

        """

        exporter = exporters.DMSExporter(existing_handling=existing_handling)

        if not self._client:
            raise NeatSessionError("No client provided!")

        conversion_issues = IssueList(action="to.cdf.data_model")
        with catch_warnings(conversion_issues):
            result = exporter.export_to_cdf(
                self._state.data_model.last_verified_dms_rules[1], self._client, dry_run, fallback_one_by_one
            )
        result.insert(0, UploadResultCore(name="schema", issues=conversion_issues))
        self._state.data_model.outcome.append(result)
        print("You can inspect the details with the .inspect.data_model.outcome(...) method.")
        return result
