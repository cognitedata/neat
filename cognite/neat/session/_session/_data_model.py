from typing import Any, Literal
from zipfile import Path

import networkx as nx
from IPython.display import HTML, display
from pyvis.network import Network as PyVisNetwork  # type: ignore

from cognite.neat.core._constants import IN_NOTEBOOK, IN_PYODIDE
from cognite.neat.core._data_model import importers
from cognite.neat.core._data_model.analysis._base import DataModelAnalysis
from cognite.neat.core._data_model.importers._base import BaseImporter
from cognite.neat.core._data_model.models.conceptual._verified import ConceptualDataModel
from cognite.neat.core._data_model.models.physical._verified import PhysicalDataModel
from cognite.neat.core._issues._base import IssueList
from cognite.neat.core._issues.errors._general import NeatValueError
from cognite.neat.core._issues.warnings._general import MissingCogniteClientWarning
from cognite.neat.core._utils.io_ import to_directory_compatible
from cognite.neat.core._utils.rdf_ import uri_display_name
from cognite.neat.core._utils.reader._base import NeatReader
from cognite.neat.plugins._manager import get_plugin_manager
from cognite.neat.plugins.data_model.importers._base import DataModelImporterPlugin
from cognite.neat.session._show import _generate_hex_color_per_type
from cognite.neat.session._state import SessionState
from cognite.neat.session.exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class DataModelAPI:
    """API for managing data models in NEAT session."""

    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.read = ReadAPI(state)
        self.show = ShowAPI(state)

    @property
    def physical(self) -> PhysicalDataModel | None:
        """Access to the physical data model level."""
        return self._state.data_model_store.try_get_last_physical_data_model

    @property
    def conceptual(self) -> ConceptualDataModel | None:
        """Access to the conceptual data model level."""
        return self._state.data_model_store.try_get_last_conceptual_data_model

    def _repr_html_(self) -> str:
        if self._state.data_model_store.empty:
            return (
                "<strong>No data model</strong>. Get started by reading data model with the <em>.read</em> attribute."
            )

        output = []

        if self._state.data_model_store.provenance:
            if self.physical:
                html = self.physical._repr_html_()
            if self.conceptual:
                html = self.conceptual._repr_html_()
            output.append(f"<H2>Data Model</H2><br />{html}")  # type: ignore

        return "<br />".join(output)


@session_class_wrapper
class ReadAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(self, name: str, io: str | Path, **kwargs: Any) -> IssueList:
        """Provides access to the external plugins for data model importing.

        Args:
            name (str): The name of format (e.g. Excel) plugin is handling.
            io (str | Path | None): The input/output interface for the plugin.
            **kwargs (Any): Additional keyword arguments for the plugin.

        !!! note "kwargs"
            Users must consult the documentation of the plugin to understand
            what keyword arguments are supported.
        """

        # These are internal readers that are not plugins
        if name.strip().lower() == "excel":
            return self.excel(io, **kwargs)
        elif name.strip().lower() == "ontology":
            return self.ontology(io)
        elif name.strip().lower() == "yaml":
            return self.yaml(io, **kwargs)
        else:
            return self._plugin(name, io, **kwargs)

    def _plugin(self, name: str, io: str | Path, **kwargs: Any) -> IssueList:
        """Provides access to the external plugins for data model importing.

        Args:
            name (str): The name of format (e.g. Excel) plugin is handling.
            io (str | Path | None): The input/output interface for the plugin.
            **kwargs (Any): Additional keyword arguments for the plugin.

        !!! note "kwargs"
            Users must consult the documentation of the plugin to understand
            what keyword arguments are supported.
        """

        # Some plugins may not support the io argument
        reader = NeatReader.create(io)
        path = reader.materialize_path()

        self._state._raise_exception_if_condition_not_met(
            "Data Model Read",
            empty_data_model_store_required=True,
        )

        plugin_manager = get_plugin_manager()
        plugin = plugin_manager.get(name, DataModelImporterPlugin)

        print(
            f"You are using an external plugin {plugin.__name__}, which is not developed by the NEAT team."
            "\nUse it at your own risk."
        )

        return self._state.data_model_import(plugin().configure(io=path, **kwargs))

    def excel(self, io: str | Path, *, enable_manual_edit: bool = False) -> IssueList:
        """Reads a Neat Excel Data Model to the data model store.
        The data model spreadsheets may contain conceptual or physical data model definitions.

            Args:
                io: file path to the Excel sheet
                enable_manual_edit: If True, the user will be able to re-import data model
                    which where edit outside of NeatSession
        """
        reader = NeatReader.create(io)
        path = reader.materialize_path()

        self._state._raise_exception_if_condition_not_met(
            "Read Excel Data Model",
            empty_data_model_store_required=not enable_manual_edit,
        )

        return self._state.data_model_import(importers.ExcelImporter(path), enable_manual_edit)

    def ontology(self, io: str | Path) -> IssueList:
        """Reads an OWL ontology source into NeatSession.

        Args:
            io: file path or url to the OWL file
        """

        self._state._raise_exception_if_condition_not_met(
            "Read Ontology",
            empty_data_model_store_required=True,
        )

        reader = NeatReader.create(io)
        importer = importers.OWLImporter.from_file(reader.materialize_path(), source_name=f"file {reader!s}")
        return self._state.data_model_import(importer)

    def yaml(self, io: str | Path, *, format: Literal["neat", "toolkit"] = "neat") -> IssueList:
        """Reads a yaml with either neat data mode, or several toolkit yaml files to
        import Data Model(s) into NeatSession.

        Args:
            io: File path to the Yaml file in the case of "neat" yaml, or path to a zip folder or directory with several
                Yaml files in the case of "toolkit".
            format: The format of the yaml file(s). Can be either "neat" or "toolkit".

        Example:
            ```python
            neat.read.yaml("path_to_toolkit_yamls")
            ```
        """
        self._state._raise_exception_if_condition_not_met(
            "Read YAML data model",
            empty_data_model_store_required=True,
        )
        reader = NeatReader.create(io)
        path = reader.materialize_path()
        importer: BaseImporter
        if format == "neat":
            importer = importers.DictImporter.from_yaml_file(path, source_name=f"{reader!s}")
        elif format == "toolkit":
            dms_importer = importers.DMSImporter.from_path(path, self._state.client)
            if dms_importer.issue_list.has_warning_type(MissingCogniteClientWarning):
                raise NeatSessionError(
                    "No client provided. You are referencing Cognite containers in your data model, "
                    "NEAT needs a client to lookup the container definitions. "
                    "Please set the client in the session, NeatSession(client=client)."
                )
            importer = dms_importer
        else:
            raise NeatValueError(f"Unsupported YAML format: {format}")
        return self._state.data_model_import(importer)


@session_class_wrapper
class ShowAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(self) -> Any:
        """Generates a visualization of the data model without implements."""
        if self._state.data_model_store.empty:
            raise NeatSessionError("No data model available. Try using [bold].read[/bold] to read a data model.")

        last_target = self._state.data_model_store.provenance[-1].target_entity
        data_model = last_target.physical or last_target.conceptual
        analysis = DataModelAnalysis(physical=last_target.physical, conceptual=last_target.conceptual)

        if last_target.physical is not None:
            di_graph = analysis._physical_di_graph(format="data-model")
        else:
            di_graph = analysis._conceptual_di_graph(format="data-model")

        identifier = to_directory_compatible(str(data_model.metadata.identifier))
        name = f"{identifier}.html"
        return self._generate_visualization(di_graph, name)

    def implements(self) -> Any:
        """Generates a visualization of implements of the data model concepts, showing
        the inheritance between the concepts in the data model."""
        if self._state.data_model_store.empty:
            raise NeatSessionError("No data model available. Try using [bold].read[/bold] to read a data model.")

        last_target = self._state.data_model_store.provenance[-1].target_entity
        data_model = last_target.physical or last_target.conceptual
        analysis = DataModelAnalysis(physical=last_target.physical, conceptual=last_target.conceptual)

        if last_target.physical is not None:
            di_graph = analysis._physical_di_graph(format="implements")
        else:
            di_graph = analysis._conceptual_di_graph(format="implements")
        identifier = to_directory_compatible(str(data_model.metadata.identifier))
        name = f"{identifier}_implements.html"
        return self._generate_visualization(di_graph, name)

    def provenance(self) -> Any:
        if not self._state.data_model_store.provenance:
            raise NeatSessionError("No data model available. Try using [bold].read[/bold] to load data model.")

        di_graph = self._generate_provenance_di_graph()
        unique_hash = self._state.data_model_store.calculate_provenance_hash(shorten=True)
        return self._generate_visualization(di_graph, name=f"data_model_provenance_{unique_hash}.html")

    def _generate_visualization(self, di_graph: nx.DiGraph, name: str) -> Any:
        if not IN_NOTEBOOK:
            raise NeatSessionError("Visualization is only available in Jupyter notebooks!")

        net = PyVisNetwork(
            notebook=IN_NOTEBOOK,
            cdn_resources="remote",
            directed=True,
            height="750px",
            width="100%",
            select_menu=IN_NOTEBOOK,
        )

        # Change the plotting layout
        net.repulsion(
            node_distance=100,
            central_gravity=0.3,
            spring_length=200,
            spring_strength=0.05,
            damping=0.09,
        )

        net.from_nx(di_graph)
        if IN_PYODIDE:
            net.write_html(name)
            return display(HTML(name))

        else:
            return net.show(name)

    def _generate_provenance_di_graph(self) -> nx.DiGraph:
        di_graph = nx.DiGraph()
        hex_colored_types = _generate_hex_color_per_type(["Agent", "Entity", "Activity", "Export", "Pruned"])

        for change in self._state.data_model_store.provenance:
            source = uri_display_name(change.source_entity.id_)
            target = uri_display_name(change.target_entity.id_)
            agent = uri_display_name(change.agent.id_)

            di_graph.add_node(
                source,
                label=source,
                type="Entity",
                title="Entity",
                color=hex_colored_types["Entity"],
            )

            di_graph.add_node(
                target,
                label=target,
                type="Entity",
                title="Entity",
                color=hex_colored_types["Entity"],
            )

            di_graph.add_node(
                agent,
                label=agent,
                type="Agent",
                title="Agent",
                color=hex_colored_types["Agent"],
            )

            di_graph.add_edge(source, agent, label="used", color="grey")
            di_graph.add_edge(agent, target, label="generated", color="grey")

        for (
            source_id,
            exports,
        ) in self._state.data_model_store.exports_by_source_entity_id.items():
            source_shorten = uri_display_name(source_id)
            for export in exports:
                export_id = uri_display_name(export.target_entity.id_)
                di_graph.add_node(
                    export_id,
                    label=export_id,
                    type="Export",
                    title="Export",
                    color=hex_colored_types["Export"],
                )
                di_graph.add_edge(source_shorten, export_id, label="exported", color="grey")

        return di_graph
