from collections.abc import Collection
from pathlib import Path
from typing import Any, Literal, overload

from cognite.client.data_classes.data_modeling import SpaceApply

from cognite.neat._client import NeatClient
from cognite.neat._constants import COGNITE_MODELS
from cognite.neat._graph import loaders
from cognite.neat._rules import exporters
from cognite.neat._rules._constants import PATTERNS
from cognite.neat._rules._shared import VerifiedRules
from cognite.neat._rules.exporters._rules2dms import Component
from cognite.neat._rules.models.dms import DMSMetadata
from cognite.neat._utils.upload import UploadResultList

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
        include_reference: bool = True,
    ) -> None:
        """Export the verified data model to Excel.

        Args:
            io: The file path or file-like object to write the Excel file to.
            include_reference: If True, the reference data model will be included. Defaults to True.
                Note that this only applies if you have created the data model using the
                .to_enterprise(), .to_solution(), or .to_data_product() methods.

        Example:
            Export information model to excel rules sheet
            ```python
            information_rules_file_name = "information_rules.xlsx"
            neat.to.excel(information_rules_file_name)
            ```

        Example:
            Read CogniteCore model, convert it to an enterprise model, and export it to an excel file
            ```python
            client = CogniteClient()
            neat = NeatSession(client)

            neat.read.cdf(("cdf_cdm", "CogniteCore", "v1"))
            neat.verify()
            neat.prepare.data_model.to_enterprise(
                data_model_id=("sp_doctrino_space", "ExtensionCore", "v1"),
                org_name="MyOrg",
                move_connections=True
            )
            dms_rules_file_name = "dms_rules.xlsx"
            neat.to.excel(dms_rules_file_name, include_reference=True)
            ```
        """
        reference_rules_with_prefix: tuple[VerifiedRules, str] | None = None
        if include_reference and self._state.last_reference:
            if (
                isinstance(self._state.last_reference.metadata, DMSMetadata)
                and self._state.last_reference.metadata.as_data_model_id() in COGNITE_MODELS
            ):
                prefix = "CDM"
            else:
                prefix = "Ref"
            reference_rules_with_prefix = self._state.last_reference, prefix

        exporter = exporters.ExcelExporter(styling="maximal", reference_rules_with_prefix=reference_rules_with_prefix)
        return self._state.rule_store.export_to_file(exporter, Path(io))

    @overload
    def yaml(self, io: None, format: Literal["neat"] = "neat", skip_system_spaces: bool = True) -> str: ...

    @overload
    def yaml(self, io: Any, format: Literal["neat", "toolkit"] = "neat", skip_system_spaces: bool = True) -> None: ...

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
            if io is None:
                return self._state.rule_store.export(exporter)

            self._state.rule_store.export_to_file(exporter, Path(io))
        elif format == "toolkit":
            if io is None or not isinstance(io, str | Path):
                raise NeatSessionError(
                    "Please provide a zip file or directory path to write the YAML files to."
                    "This is required for the 'toolkit' format."
                )
            user_path = Path(io)
            if user_path.suffix == "" and not user_path.exists():
                user_path.mkdir(parents=True)
            self._state.rule_store.export_to_file(
                exporters.DMSExporter(remove_cdf_spaces=skip_system_spaces), user_path
            )
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

        space = space or f"{self._state.rule_store.last_verified_dms_rules.metadata.space}_instances"

        if space and space == self._state.rule_store.last_verified_dms_rules.metadata.space:
            raise NeatSessionError("Space for instances must be different from the data model space.")
        elif not PATTERNS.space_compliance.match(str(space)):
            raise NeatSessionError("Please provide a valid space name. {PATTERNS.space_compliance.pattern}")

        if not self._client.data_modeling.spaces.retrieve(space):
            self._client.data_modeling.spaces.apply(SpaceApply(space=space))

        loader = loaders.DMSLoader.from_rules(
            self._state.rule_store.last_verified_dms_rules,
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

        result = self._state.rule_store.export_to_cdf(exporter, self._client, dry_run)
        print("You can inspect the details with the .inspect.outcome.data_model(...) method.")
        return result
