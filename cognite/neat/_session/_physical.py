import warnings
from types import MethodType
from typing import Any, Literal

from cognite.neat._client import NeatClient
from cognite.neat._config import NeatConfig
from cognite.neat._data_model.deployer.deployer import DeploymentOptions, SchemaDeployer
from cognite.neat._data_model.exporters import (
    DMSAPIExporter,
    DMSAPIJSONExporter,
    DMSAPIYAMLExporter,
    DMSExcelExporter,
    DMSExporter,
    DMSTableJSONExporter,
    DMSTableYamlExporter,
)
from cognite.neat._data_model.exporters._table_exporter.workbook import WorkbookOptions
from cognite.neat._data_model.importers import DMSAPICreator, DMSAPIImporter, DMSImporter, DMSTableImporter
from cognite.neat._data_model.models.dms import DataModelReference
from cognite.neat._data_model.rules.dms import DmsDataModelRulesOrchestrator
from cognite.neat._exceptions import UserInputError
from cognite.neat._state_machine import PhysicalState
from cognite.neat._store._store import NeatStore
from cognite.neat._utils._reader import NeatReader

from ._wrappers import session_wrapper


@session_wrapper
class PhysicalDataModel:
    """Read from a data source into NeatSession graph store."""

    def __init__(self, store: NeatStore, client: NeatClient, config: NeatConfig) -> None:
        self._store = store
        self._client = client
        self._config = config
        self.read = ReadPhysicalDataModel(self._store, self._client, self._config)
        self.write = WritePhysicalDataModel(self._store, self._client, self._config)

        # attach alpha methods
        if self._config.alpha.enable_solution_model_creation:
            self.create = MethodType(create, self)  # type: ignore[attr-defined]

    def _repr_html_(self) -> str:
        if not isinstance(self._store.state, PhysicalState):
            return "No physical data model. Get started by reading physical data model <em>.physica_data_mode.read</em>"

        dm = self._store.physical_data_model[-1]

        html = ["<div>"]
        html.append(
            f"<h3>Data Model: {dm.data_model.space}:{dm.data_model.external_id}(version={dm.data_model.version})</h3>"
        )
        html.append("<table style='border-collapse: collapse;'>")
        html.append("<tr><th style='text-align: left; padding: 4px; border: 1px solid #ddd;'>Component</th>")
        html.append("<th style='text-align: left; padding: 4px; border: 1px solid #ddd;'>Count</th></tr>")

        html.append("<tr><td style='padding: 4px; border: 1px solid #ddd;'>Views</td>")
        html.append(f"<td style='padding: 4px; border: 1px solid #ddd;'>{len(dm.views)}</td></tr>")

        html.append("<tr><td style='padding: 4px; border: 1px solid #ddd;'>Containers</td>")
        html.append(f"<td style='padding: 4px; border: 1px solid #ddd;'>{len(dm.containers)}</td></tr>")

        html.append("<tr><td style='padding: 4px; border: 1px solid #ddd;'>Spaces</td>")
        html.append(f"<td style='padding: 4px; border: 1px solid #ddd;'>{len(dm.spaces)}</td></tr>")

        html.append("<tr><td style='padding: 4px; border: 1px solid #ddd;'>Node Types</td>")
        html.append(f"<td style='padding: 4px; border: 1px solid #ddd;'>{len(dm.node_types)}</td></tr>")

        html.append("</table>")
        html.append("</div>")

        return "".join(html)


@session_wrapper
class ReadPhysicalDataModel:
    """Read physical data model from various sources into NeatSession store.

    Available methods:

    - `neat.physical_data_model.read.yaml`
    - `neat.physical_data_model.read.json`
    - `neat.physical_data_model.read.excel`
    - `neat.physical_data_model.read.cdf`
    """

    def __init__(self, store: NeatStore, client: NeatClient, config: NeatConfig) -> None:
        self._store = store
        self._client = client
        self._config = config

    def _create_on_success(self, fix: bool = False) -> DmsDataModelRulesOrchestrator:
        """Create the appropriate on_success handler based on whether fixes should be applied."""
        # Only apply fixes if both fix=True and the alpha flag is enabled
        apply_fixes = fix and self._config.alpha.fix_validation_issues
        if fix and not self._config.alpha.fix_validation_issues:
            warnings.warn(
                "fix=True has no effect without enabling alpha.fix_validation_issues. "
                "Set neat.config.alpha.fix_validation_issues = True to enable automatic fixes.",
                UserWarning,
                stacklevel=3,
            )
        return DmsDataModelRulesOrchestrator(
            apply_fixes=apply_fixes,
            modus_operandi=self._config.modeling.mode,
            cdf_snapshot=self._store.cdf_snapshot,
            limits=self._store.cdf_limits,
            can_run_validator=self._config.validation.can_run_validator,
            enable_alpha_validators=self._config.alpha.enable_experimental_validators,
        )

    def yaml(self, io: Any, format: Literal["neat", "toolkit"] = "neat", fix: bool = False) -> None:
        """Read physical data model from YAML file(s)

        Args:
            io (Any): The file or directory path or buffer to read from.
            format (Literal["neat", "toolkit"]): The format of the input file(s).
                - "neat": Neat's DMS table format.
                - "toolkit": Cognite DMS API format which is the format used by Cognite Toolkit.
            fix (bool): If True, automatically apply fixes for fixable issues (e.g., requires constraints).
        """

        path = NeatReader.create(io).materialize_path()

        reader: DMSImporter
        if format == "neat":
            reader = DMSTableImporter.from_yaml(path)
        elif format == "toolkit":
            reader = DMSAPIImporter.from_yaml(path)
        else:
            raise UserInputError(f"Unsupported format: {format}. Supported formats are 'neat' and 'toolkit'.")

        on_success = self._create_on_success(fix)
        return self._store.read_physical(reader, on_success)

    def json(self, io: Any, format: Literal["neat", "toolkit"] = "neat", fix: bool = False) -> None:
        """Read physical data model from JSON file(s)

        Args:
            io (Any): The file or directory path or buffer to read from.
            format (Literal["neat", "toolkit"]): The format of the input file(s).
                - "neat": Neat's DMS table format.
                - "toolkit": Cognite DMS API format which is the format used by Cognite Toolkit.
            fix (bool): If True, automatically apply fixes for fixable issues (e.g., requires constraints).
        """

        path = NeatReader.create(io).materialize_path()

        reader: DMSImporter
        if format == "neat":
            reader = DMSTableImporter.from_json(path)
        elif format == "toolkit":
            reader = DMSAPIImporter.from_json(path)
        else:
            raise UserInputError(f"Unsupported format: {format}. Supported formats are 'neat' and 'toolkit'.")

        on_success = self._create_on_success(fix)
        return self._store.read_physical(reader, on_success)

    def excel(self, io: Any, fix: bool = False) -> None:
        """Read physical data model from Excel file

        Args:
            io (Any): The file path or buffer to read from.
            fix (bool): If True, automatically apply fixes for fixable issues (e.g., requires constraints).

        """

        path = NeatReader.create(io).materialize_path()
        reader = DMSTableImporter.from_excel(path)

        on_success = self._create_on_success(fix)
        return self._store.read_physical(reader, on_success)

    def cdf(self, space: str, external_id: str, version: str, fix: bool = False) -> None:
        """Read physical data model from CDF

        Args:
            space (str): The schema space of the data model.
            external_id (str): The external id of the data model.
            version (str): The version of the data model.
            fix (bool): If True, automatically apply fixes for fixable issues (e.g., requires constraints).

        """
        reader = DMSAPIImporter.from_cdf(
            DataModelReference(space=space, external_id=external_id, version=version), self._client
        )

        on_success = self._create_on_success(fix)
        return self._store.read_physical(reader, on_success)


@session_wrapper
class WritePhysicalDataModel:
    """Write physical data model to various sources from NeatSession store.

    Available methods:

    - `neat.physical_data_model.write.yaml`
    - `neat.physical_data_model.write.json`
    - `neat.physical_data_model.write.excel`
    - `neat.physical_data_model.write.cdf`
    """

    def __init__(self, store: NeatStore, client: NeatClient, config: NeatConfig) -> None:
        self._store = store
        self._client = client
        self._config = config

    def yaml(self, io: Any, format: Literal["neat", "toolkit"] = "neat") -> None:
        """Write physical data model to YAML file

        Args:
            io (Any): The file path or buffer to write to.
            format (Literal["neat", "toolkit"]): The format of the output file
                - "neat": Neat's DMS table format.
                - "toolkit": Cognite DMS API format which is the format used by Cognite Toolkit.
        """

        file_path = NeatReader.create(io).materialize_path()
        writer: DMSExporter
        if format == "neat":
            writer = DMSTableYamlExporter()
        elif format == "toolkit":
            writer = DMSAPIYAMLExporter()
        else:
            raise UserInputError(f"Unsupported format: {format}. Supported formats are 'neat' and 'toolkit'.")

        return self._store.write_physical(writer, file_path=file_path)

    def json(self, io: Any, format: Literal["neat", "toolkit"] = "neat") -> None:
        """Write physical data model to JSON file

        Args:
            io (Any): The file path or buffer to write to.
            format (Literal["neat", "toolkit"]): The format of the output file
                - "neat": Neat's DMS table format.
                - "toolkit": Cognite DMS API format which is the format used by Cognite Toolkit.
        """

        file_path = NeatReader.create(io).materialize_path()
        writer: DMSExporter
        if format == "neat":
            writer = DMSTableJSONExporter()
        elif format == "toolkit":
            writer = DMSAPIJSONExporter()
        else:
            raise UserInputError(f"Unsupported format: {format}. Supported formats are 'neat' and 'toolkit'.")

        return self._store.write_physical(writer, file_path=file_path)

    def excel(self, io: Any, skip_other_spaces: bool = True) -> None:
        """Write physical data model to Excel file

        Args:
            io (Any): The file path or buffer to write to.
            skip_other_spaces (bool): If true, only properties in the same space as the data model will be written.

        """

        file_path = NeatReader.create(io).materialize_path()
        options = WorkbookOptions(skip_properties_in_other_spaces=skip_other_spaces)
        writer = DMSExcelExporter(options=options)

        return self._store.write_physical(writer, file_path=file_path)

    def cdf(self, dry_run: bool = True, rollback: bool = False, drop_data: bool = False) -> None:
        """Write physical data model with views, containers, and spaces that are in the same space as the data model
        to CDF.

        Args:
            dry_run (bool): If true, the changes will not be applied to CDF. Instead, Neat will
                report what changes would have been made.
            rollback (bool): If true, all changes will be rolled back if any error occurs.
            drop_data (bool): Only applicable if the session mode is 'rebuild'. If

        !!! note "Impact of governance profile"
            This method depends on the session governance profile for data modeling set when creating the NeatSession:

            - In `additive` mode, only new or updates to data models/views/containers will be applied.
              You cannot remove views from data models, properties from views or containers, or
              indexes or constraints from containers.

            - In `rebuild` mode, the data model in CDF will be made to exactly match the data model in Neat.
              If there are any breaking changes, Neat will delete and recreate the relevant
              data model/view/container. However, if drop_data is set to False, Neat will treat
              containers as `additive` and will not delete any containers or remove properties,
              indexes, or constraints. To fully rebuild the data model, including containers, set drop_data to True.
        """
        writer = DMSAPIExporter()
        options = DeploymentOptions(
            dry_run=dry_run,
            auto_rollback=rollback,
            drop_data=drop_data,
            modus_operandi=self._config.modeling.mode,
        )
        on_success = SchemaDeployer(self._client, options)
        return self._store.write_physical(writer, on_success)


def create(
    self: PhysicalDataModel,
    space: str,
    external_id: str,
    version: str,
    views: list[str],
    name: str | None = None,
    description: str | None = None,
    kind: Literal["solution"] = "solution",
    fix: bool = False,
) -> None:
    """Create a solution data model in Neat from CDF views.

    Args:
        space (str): The schema space of the data model.
        external_id (str): The external id of the data model.
        version (str): The version of the data model.
        views (list[str]): List of view external ids to include in the data model in the short string format
            space:external_id(version=version)
        name (str | None): The name of the data model. If None, the name will be fetched from CDF.
        description (str | None): The description of the data model. If None, the description will be fetched from CDF.
        kind (Literal["solution"]): The kind of the data model. Currently, only "solution" is supported.
        fix (bool): If True, automatically apply fixes for fixable issues (e.g., requires constraints).
    """

    if not self._store.cdf_snapshot.data_model:
        raise ValueError("There are no data models in CDF. Cannot create solution model.")

    creator = DMSAPICreator(
        space=space,
        external_id=external_id,
        version=version,
        views=views,
        name=name,
        description=description,
        kind=kind,
        cdf_snapshot=self._store.cdf_snapshot,
    )

    on_success = self.read._create_on_success(fix)
    return self._store.read_physical(creator, on_success)
