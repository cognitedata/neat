import warnings
from pathlib import Path
from typing import Any, Literal, cast, overload

from cognite.client.data_classes.data_modeling import DataModelIdentifier

from cognite.neat.core._client._api_client import NeatClient
from cognite.neat.core._constants import COGNITE_MODELS
from cognite.neat.core._data_model import exporters
from cognite.neat.core._data_model._shared import VerifiedDataModel
from cognite.neat.core._data_model.importers._dms2data_model import DMSImporter
from cognite.neat.core._data_model.models.conceptual._verified import ConceptualDataModel
from cognite.neat.core._data_model.models.physical._verified import PhysicalDataModel, PhysicalMetadata
from cognite.neat.core._issues._base import IssueList
from cognite.neat.core._issues._contextmanagers import catch_issues
from cognite.neat.core._utils.auxiliary import filter_kwargs_by_method
from cognite.neat.core._utils.reader._base import NeatReader
from cognite.neat.core._utils.upload import UploadResultList
from cognite.neat.session._state import SessionState
from cognite.neat.session.exceptions import NeatSessionError, session_class_wrapper

InternalWriterName = Literal["excel", "ontology", "shacl", "cdf", "yaml"]


@session_class_wrapper
class WriteAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(
        self, name: str, io: str | Path | None = None, **kwargs: Any
    ) -> str | UploadResultList | IssueList | None:
        """Provides access to the writers for exporting data models to different formats.

        Args:
            name (str): The name of format (e.g. Excel) writer is handling.
            io (str | Path | None): The input/output interface for the writer.
            **kwargs (Any): Additional keyword arguments for the writer.

        !!! note "kwargs"
            Users must consult the documentation of the writer
            to understand what keyword arguments are supported.
        """

        # Clean the input name once before matching.
        clean_name: InternalWriterName | str = name.strip().lower()

        match clean_name:
            case "excel":
                if io is None:
                    raise NeatSessionError("'io' parameter is required for Excel format.")
                return self.excel(cast(str | Path, io), **filter_kwargs_by_method(kwargs, self.excel))
            case "cdf":
                return self.cdf(**filter_kwargs_by_method(kwargs, self.cdf))
            case "yaml":
                return self.yaml(io, **filter_kwargs_by_method(kwargs, self.yaml))
            case "ontology":
                if io is None:
                    raise NeatSessionError("'io' parameter is required for ontology format.")
                self.ontology(cast(str | Path, io))
                return None
            case "shacl":
                if io is None:
                    raise NeatSessionError("'io' parameter is required for SHACL format.")
                self.shacl(cast(str | Path, io))
                return None
            case _:
                raise NeatSessionError(
                    f"Unsupported data model writer: {name}. "
                    "Please use one of the following: 'excel', 'cdf', 'yaml', 'ontology', 'shacl'."
                )

    def excel(
        self,
        io: str | Path,
        *,
        include_reference: bool | DataModelIdentifier = True,
        include_properties: Literal["same-space", "all"] = "all",
        add_empty_rows: bool = False,
    ) -> IssueList | None:
        """Export the verified data model to Excel.

        Args:
            io: The file path or file-like object to write the Excel file to.
            include_reference: If True, the reference data model will be included. Defaults to True.
                Note that this only applies if you have created the data model using the
                create.enterprise_model(...), create.solution_model(), or create.data_product_model() methods.
                You can also provide a DataModelIdentifier directly, which will be read from CDF
            include_properties: The properties to include in the Excel file. Defaults to "all".
                - "same-space": Only properties that are in the same space as the data model will be included.
            add_empty_rows: If True, empty rows will be added between each component. Defaults to False.

        Example:
            Export conceptual data model to an Excel file
            ```python
            conceptual_dm_file_name = "conceptual_data_model.xlsx"
            neat.data_model.write.excel(conceptual_dm_file_name)
            ```

        Example:
            Read CogniteCore model, convert it to an enterprise model, and export it to an excel file
            ```python
            client = CogniteClient()
            neat = NeatSession(client)

            neat.data_model.read.cdf(("cdf_cdm", "CogniteCore", "v1"))
            neat.data_model.create.enterprise_model(
                data_model_id=("sp_doctrino_space", "ExtensionCore", "v1"),
                org_name="MyOrg",
            )
            physical_dm_file_name = "physical_dm.xlsx"
            neat.data_model.write.excel(physical_dm_file_name, include_reference=True)
            ```

        Example:
            Read the data model ("my_space", "ISA95Model", "v5") and export it to an excel file with the
            CogniteCore model in the reference sheets.
            ```python
            client = CogniteClient()
            neat = NeatSession(client)

            neat.data_model.read.cdf(("my_space", "ISA95Model", "v5"))
            physical_dm_file_name = "physical_dm.xlsx"
            neat.data_model.write.excel(physical_dm_file_name, include_reference=("cdf_cdm", "CogniteCore", "v1"))
        """
        reference_data_model_with_prefix: tuple[VerifiedDataModel, str] | None = None
        include_properties = include_properties.strip().lower()
        if include_properties not in ["same-space", "all"]:
            raise NeatSessionError(
                f"Invalid include_properties value: '{include_properties}'. Must be 'same-space' or 'all'."
            )

        if include_reference is not False:
            if include_reference is True and self._state.last_reference is not None:
                ref_data_model: ConceptualDataModel | PhysicalDataModel | None = self._state.last_reference
            elif include_reference is True:
                ref_data_model = None
            else:
                if not self._state.client:
                    raise NeatSessionError("No client provided!")
                ref_data_model = None
                with catch_issues() as issues:
                    ref_read = DMSImporter.from_data_model_id(self._state.client, include_reference).to_data_model()
                    if ref_read.unverified_data_model is not None:
                        ref_data_model = ref_read.unverified_data_model.as_verified_data_model()
                if ref_data_model is None or issues.has_errors:
                    issues.action = f"Read {include_reference}"
                    return issues
            if ref_data_model is not None:
                prefix = "Ref"
                if (
                    isinstance(ref_data_model.metadata, PhysicalMetadata)
                    and ref_data_model.metadata.as_data_model_id() in COGNITE_MODELS
                ):
                    prefix = "CDM"
                reference_data_model_with_prefix = ref_data_model, prefix

        exporter = exporters.ExcelExporter(
            styling="maximal",
            reference_data_model_with_prefix=reference_data_model_with_prefix,
            add_empty_rows=add_empty_rows,
            include_properties=cast(Literal["same-space", "all"], include_properties),
        )
        self._state.data_model_store.export_to_file(exporter, NeatReader.create(io).materialize_path())
        return None

    def cdf(
        self,
        *,
        existing: Literal["fail", "skip", "update", "force", "recreate"] = "update",
        dry_run: bool = False,
        drop_data: bool = False,
    ) -> UploadResultList:
        """Export the verified DMS data model to CDF.

        Args:
            existing: What to do if the component already exists. Defaults to "update".
                See the note below for more information about the options.
            dry_run: If True, no changes will be made to CDF. Defaults to False.
            drop_data: If existing is 'force' or 'recreate' and the operation will lead to data loss,
                the component will be skipped unless drop_data is True. Defaults to False.
                Note this only applies to spaces and containers if they contain data.

        !!! note "Data Model creation modes"
            - "fail": If any component already exists, the export will fail.
            - "skip": If any component already exists, it will be skipped.
            - "update": If any component already exists, it will be updated. For data models, views, and containers
                this means combining the existing and new component. Fo example, for data models the new
                views will be added to the existing views.
            - "force": If any component already exists, and the update fails, it will be deleted and recreated.
            - "recreate": All components will be deleted and recreated. The exception is spaces, which will be updated.

        """

        self._state._raise_exception_if_condition_not_met(
            "Export DMS data model to CDF",
            client_required=True,
        )

        exporter = exporters.DMSExporter(existing=existing, drop_data=drop_data)

        result = self._state.data_model_store.export_to_cdf(exporter, cast(NeatClient, self._state.client), dry_run)
        print("You can inspect the details with the .inspect.outcome.data_model(...) method.")
        return result

    @overload
    def yaml(
        self,
        io: None,
        *,
        format: Literal["neat", "toolkit"] = "neat",
        skip_system_spaces: bool = True,
    ) -> str: ...

    @overload
    def yaml(
        self,
        io: str | Path,
        *,
        format: Literal["neat", "toolkit"] = "neat",
        skip_system_spaces: bool = True,
    ) -> None: ...

    def yaml(
        self,
        io: str | Path | None = None,
        *,
        format: Literal["neat", "toolkit"] = "neat",
        skip_system_spaces: bool = True,
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
            your_yaml_file_name = "neat_dm.yaml"
            neat.data_model.write.yaml(your_yaml_file_name, format="neat")
            ```

        Example:
            Export yaml files as a zip folder in the case of "toolkit" format
            ```python
            your_zip_folder_name = "toolkit_data_model_files.zip"
            neat.data_model.write.yaml(your_zip_folder_name, format="toolkit")
            ```

        Example:
            Export yaml files to a folder in the case of "toolkit" format
            ```python
            your_folder_name = "my_project/data_model_files"
            neat.data_model.write.yaml(your_folder_name, format="toolkit")
            ```
        """

        if format == "neat":
            exporter = exporters.YAMLExporter()
            if io is None:
                return self._state.data_model_store.export(exporter)

            self._state.data_model_store.export_to_file(exporter, NeatReader.create(io).materialize_path())
        elif format == "toolkit":
            if io is None:
                raise NeatSessionError(
                    "Please provide a zip file or directory path to write the YAML files to."
                    "This is required for the 'toolkit' format."
                )
            user_path = NeatReader.create(io).materialize_path()
            if user_path.suffix == "" and not user_path.exists():
                user_path.mkdir(parents=True)
            self._state.data_model_store.export_to_file(
                exporters.DMSExporter(remove_cdf_spaces=skip_system_spaces), user_path
            )
        else:
            raise NeatSessionError("Please provide a valid format. 'neat' or 'toolkit'")

        return None

    def ontology(self, io: str | Path) -> None:
        """Write out data model as OWL ontology.

        Args:
            io: The file path to file-like object to write the session to.

        Example:
            Export the session to a file
            ```python
            ontology_file_name = "neat_session.ttl"
            neat.data_model.write.ontology(ontology_file_name)
            ```
        """

        filepath = self._prepare_ttl_filepath(io)
        exporter = exporters.OWLExporter()
        self._state.data_model_store.export_to_file(exporter, filepath)
        return None

    def shacl(self, io: str | Path) -> None:
        """Write out data model as SHACL shapes.

        Args:
            io: The file path to file-like object to write the session to.

        Example:
            Export the session to a file
            ```python
            shacl_file_name = "neat_session.shacl.ttl"
            neat.data_model.write.shacl(shacl_file_name)
            ```
        """

        filepath = self._prepare_ttl_filepath(io)
        exporter = exporters.SHACLExporter()
        self._state.data_model_store.export_to_file(exporter, filepath)
        return None

    def _prepare_ttl_filepath(self, io: str | Path) -> Path:
        """Ensures the filepath has a .ttl extension, adding it if missing."""
        filepath = NeatReader.create(io).materialize_path()
        if filepath.suffix != ".ttl":
            warnings.filterwarnings("default")
            warnings.warn("File extension is not .ttl, adding it to the file name", stacklevel=2)
            filepath = filepath.with_suffix(".ttl")
        return filepath
