from collections.abc import Collection
from pathlib import Path
from typing import Any, Literal, overload

from cognite.client.data_classes.data_modeling import SpaceApply

from cognite.neat._client import NeatClient
from cognite.neat._graph import loaders
from cognite.neat._issues import IssueList, catch_warnings
from cognite.neat._rules import exporters
from cognite.neat._rules._constants import PATTERNS
from cognite.neat._rules._shared import VerifiedRules
from cognite.neat._rules.exporters._rules2dms import Component
from cognite.neat._utils.upload import UploadResultCore, UploadResultList

from ._state import SessionState
from .exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class ToAPI:
    """API used to write the contents of a NeatSession to a specified destination. For instance writing information
    rules or DMS rules to a NEAT rules Excel spreadsheet, or writing a verified data model to CDF.

    """

    def __init__(self, state: SessionState, client: NeatClient | None, verbose: bool) -> None:
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

        Example:
            Export information model to excel rules sheet
            ```python
            information_rules_file_name = "information_rules.xlsx"
            neat.to.excel(information_rules_file_name, model="information")
            ```

        Example:
            Export data model to excel rules sheet
            ```python
            dms_rules_file_name = "dms_rules.xlsx"
            neat.to.excel(information_rules_file_name, model="dms")
            ```
        """
        exporter = exporters.ExcelExporter(styling="maximal")
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

    def yaml(
        self, io: Any | None = None, format: Literal["neat", "toolkit"] = "neat", skip_system_spaces: bool = True
    ) -> str | None:
        """Export the verified data model to YAML.

        Args:
            io: The file path or file-like object to write the YAML file to. Defaults to None.
            format: The format of the YAML file. Defaults to "neat".
            skip_system_spaces: If True, system spaces will be skipped. Defaults to True.

        !!! note "YAML formats"
            - "neat": This is the format Neat uses to store the data model.
            - "toolkit": This is the format used by Cognite Toolkit, that matches the CDF API.

        Returns:
            str | None: If io is None, the YAML string will be returned. Otherwise, None will be returned.

        Example:
            Export to yaml file in the case of "neat" format
            ```python
            your_yaml_file_name = "neat_rules.yaml"
            neat.to.yaml(your_yaml_file_name, format="neat")
            ```

        Example:
            Export yaml files as a zip folder in the case of "toolkit" format
            ```python
            your_zip_folder_name = "toolkit_data_model_files.zip"
            neat.to.yaml(your_zip_folder_name, format="toolkit")
            ```

        Example:
            Export yaml files to a folder in the case of "toolkit" format
            ```python
            your_folder_name = "my_project/data_model_files"
            neat.to.yaml(your_folder_name, format="toolkit")
            ```
        """
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
            user_path = Path(io)
            if user_path.suffix == "" and not user_path.exists():
                user_path.mkdir(parents=True)
            exporters.DMSExporter(remove_cdf_spaces=skip_system_spaces).export_to_file(dms_rule, user_path)
        else:
            raise NeatSessionError("Please provide a valid format. 'neat' or 'toolkit'")

        return None


@session_class_wrapper
class CDFToAPI:
    """Write a verified Data Model and Instances to CDF."""

    def __init__(self, state: SessionState, client: NeatClient | None, verbose: bool) -> None:
        self._client = client
        self._state = state
        self._verbose = verbose

    def instances(self, space: str | None = None) -> UploadResultList:
        """Export the verified DMS instances to CDF.

        Args:
            space: Name of instance space to use. Default is to suffix the schema space with '_instances'.
            Note this space is required to be different than the space with the data model.

        """
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
            client=self._client,
        )
        result = loader.load_into_cdf(self._client)
        self._state.instances.outcome.append(result)
        print("You can inspect the details with the .inspect.outcome.instances(...) method.")
        return result

    def data_model(
        self,
        existing: Literal["fail", "skip", "update", "force", "recreate"] = "update",
        dry_run: bool = False,
        drop_data: bool = False,
        components: Component | Collection[Component] | None = None,
    ) -> UploadResultList:
        """Export the verified DMS data model to CDF.

        Args:
            existing: What to do if the component already exists. Defaults to "update".
                See the note below for more information about the options.
            dry_run: If True, no changes will be made to CDF. Defaults to False.
            drop_data: If existing is 'force' or 'recreate' and the operation will lead to data loss,
                the component will be skipped unless drop_data is True. Defaults to False.
                Note this only applies to spaces and containers if they contain data.
            components: The components to export. If None, all components will be exported. Defaults to None.

        !!! note "Data Model creation modes"
            - "fail": If any component already exists, the export will fail.
            - "skip": If any component already exists, it will be skipped.
            - "update": If any component already exists, it will be updated.
            - "force": If any component already exists, and the update fails, it will be deleted and recreated.
            - "recreate": All components will be deleted and recreated. The exception is spaces, which will be updated.

        """

        exporter = exporters.DMSExporter(existing=existing, export_components=components, drop_data=drop_data)

        if not self._client:
            raise NeatSessionError("No client provided!")

        conversion_issues = IssueList(action="to.cdf.data_model")
        with catch_warnings(conversion_issues):
            result = exporter.export_to_cdf(self._state.data_model.last_verified_dms_rules[1], self._client, dry_run)
        result.insert(0, UploadResultCore(name="schema", issues=conversion_issues))
        self._state.data_model.outcome.append(result)
        print("You can inspect the details with the .inspect.outcome.data_model(...) method.")
        return result
