import warnings
from pathlib import Path
from typing import Any, Literal, cast

import networkx as nx
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import DataModelIdentifier
from IPython.display import HTML, display
from pyvis.network import Network as PyVisNetwork  # type: ignore

from thisisneat.core._constants import COGNITE_MODELS, IN_NOTEBOOK, IN_PYODIDE
from thisisneat.core._data_model import exporters, importers
from thisisneat.core._data_model._shared import VerifiedDataModel
from thisisneat.core._data_model.analysis._base import DataModelAnalysis
from thisisneat.core._data_model.importers._base import BaseImporter
from thisisneat.core._data_model.importers._dms2data_model import DMSImporter
from thisisneat.core._data_model.models.conceptual._verified import ConceptualDataModel
from thisisneat.core._data_model.models.physical._verified import (
    PhysicalDataModel,
    PhysicalMetadata,
)
from thisisneat.core._data_model.transformers._converters import (
    ConceptualToPhysical,
    MergeConceptualDataModels,
    MergePhysicalDataModels,
    ToDMSCompliantEntities,
)
from thisisneat.core._data_model.transformers._verification import (
    VerifyConceptualDataModel,
)
from thisisneat.core._issues._base import IssueList
from thisisneat.core._issues._contextmanagers import catch_issues
from thisisneat.core._store._data_model import DataModelEntity
from thisisneat.core._utils.io_ import to_directory_compatible
from thisisneat.core._utils.rdf_ import uri_display_name
from thisisneat.core._utils.reader._base import NeatReader
from thisisneat.plugins._manager import get_plugin_manager
from thisisneat.plugins.data_model.importers._base import DataModelImporterPlugin
from thisisneat.session._show import _generate_hex_color_per_type
from thisisneat.session._state import SessionState
from thisisneat.session.exceptions import NeatSessionError, session_class_wrapper


@session_class_wrapper
class ConceptualDataModelAPI:
    """API for managing data models in NEAT session."""

    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.read = ReadAPI(state)
        self.write = WriteAPI(state)
        self.show = ShowAPI(state)

    def __call__(self) -> ConceptualDataModel | None:
        """Access to the conceptual data model level."""
        return self._state.data_model_store.try_get_last_conceptual_data_model

    def _repr_html_(self) -> str:
        if conceptual := self._state.data_model_store.try_get_last_conceptual_data_model:
            output = []
            html = cast(ConceptualDataModel, conceptual)._repr_html_()
            output.append(f"<H2>Data Model</H2><br />{html}")

            return "<br />".join(output)

        return "<strong>No conceptual data model</strong>."

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
        self,
        model_id: dm.DataModelId | tuple[str, str, str],
        max_number_of_instance: int = 100,
    ) -> IssueList:
        # Temporary keeping the old inference method in case we need to revert back
        model_id = dm.DataModelId.load(model_id)
        importer = importers.InferenceImporter.from_graph_store(
            store=self._state.instances.store,
            max_number_of_instance=max_number_of_instance,
            data_model_id=model_id,
        )
        return self._state.data_model_import(importer)

    def _infer_subclasses(
        self,
        model_id: dm.DataModelId | tuple[str, str, str] = (
            "neat_space",
            "NeatInferredDataModel",
            "v1",
        ),
    ) -> IssueList:
        """Infer data model from instances."""
        last_entity: DataModelEntity | None = None
        if self._state.data_model_store.provenance:
            last_entity = self._state.data_model_store.provenance[-1].target_entity

        # Note that this importer behaves as a transformer in the data model store when there
        # is an existing data model.
        # We are essentially transforming the last entity's conceptual data model
        # into a new conceptual data model.
        importer = importers.SubclassInferenceImporter(
            issue_list=IssueList(),
            graph=self._state.instances.store.graph(),
            data_model=last_entity.conceptual if last_entity is not None else None,
            data_model_id=(dm.DataModelId.load(model_id) if last_entity is None else None),
        )

        def action() -> tuple[ConceptualDataModel, PhysicalDataModel | None]:
            unverified_conceptual = importer.to_data_model()
            unverified_conceptual = ToDMSCompliantEntities(rename_warning="raise").transform(unverified_conceptual)

            extra_conceptual = VerifyConceptualDataModel().transform(unverified_conceptual)
            if not last_entity:
                return extra_conceptual, None
            merged_conceptual = MergeConceptualDataModels(extra_conceptual).transform(last_entity.conceptual)
            if not last_entity.physical:
                return merged_conceptual, None

            extra_physical = ConceptualToPhysical(reserved_properties="warning", client=self._state.client).transform(
                extra_conceptual
            )

            merged_physical = MergePhysicalDataModels(extra_physical).transform(last_entity.physical)
            return merged_conceptual, merged_physical

        return self._state.data_model_store.do_activity(action, importer)


@session_class_wrapper
class ReadAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(self, name: str, io: str | Path, **kwargs: Any) -> IssueList:
        """Provides access to external data model reader plugins.

        Args:
            name (str): The name of format (e.g. Excel) reader is handling.
            io (str | Path | None): The input/output interface for the reader.
            **kwargs (Any): Additional keyword arguments for the reader.

        !!! note "io"
            The `io` parameter can be a file path, sting, or a DataModelIdentifier
            depending on the reader's requirements.

        !!! note "kwargs"
            Users must consult the documentation of the reader to understand
            what keyword arguments are supported.
        """

        # Clean the input name once before matching.

        return self._plugin(name, cast(str | Path, io), **kwargs)

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

    def excel(self, io: str | Path, enable_manual_edit: bool = False) -> IssueList:
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

    def yaml(
        self,
        io: str | Path,
    ) -> IssueList:
        """Reads a yaml with either neat data mode, or several toolkit yaml files to
        import Data Model(s) into NeatSession.

        Args:
            io: File path to the Yaml file in the case of "neat" yaml, or path to a zip folder or directory with several
                Yaml files in the case of "toolkit".

        Example:
            ```python
            neat.read.yaml("path_to_neat_yamls")
            ```
        """
        self._state._raise_exception_if_condition_not_met(
            "Read YAML data model",
            empty_data_model_store_required=True,
        )
        reader = NeatReader.create(io)
        path = reader.materialize_path()
        importer: BaseImporter

        importer = importers.DictImporter.from_yaml_file(path, source_name=f"{reader!s}")
        return self._state.data_model_import(importer)


@session_class_wrapper
class WriteAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def excel(
        self,
        io: str | Path,
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

    def yaml(
        self,
        io: str | Path | None = None,
    ) -> str | None:
        """Export the verified data model to YAML.

        Args:
            io: The file path or file-like object to write the YAML file to. Defaults to None.
            format: The format of the YAML file. Defaults to "neat".

        Returns:
            str | None: If io is None, the YAML string will be returned. Otherwise, None will be returned.
        """

        exporter = exporters.YAMLExporter()
        if io is None:
            return self._state.data_model_store.export(exporter)

        self._state.data_model_store.export_to_file(exporter, NeatReader.create(io).materialize_path())
        return None

    def ontology(self, io: str | Path) -> None:
        """Write out data model as OWL ontology.

        Args:
            io: The file path to file-like object to write the session to.
        """

        filepath = self._prepare_ttl_filepath(io)
        exporter = exporters.OWLExporter()
        self._state.data_model_store.export_to_file(exporter, filepath)
        return None

    def shacl(self, io: str | Path | None = None) -> None | str:
        """Write out data model as SHACL shapes.

        Args:
            io: The file path to file-like object to write the session to.

        """

        self._state._raise_exception_if_condition_not_met(
            "SHACL Export",
            has_conceptual_data_model=True,
            multi_value_type_properties_allowed=False,
            unknown_value_type_properties_allowed=False,
        )
        exporter = exporters.SHACLExporter()

        if io is None:
            return self._state.data_model_store.export(exporter).serialize(format="turtle")
        filepath = self._prepare_ttl_filepath(io)
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


@session_class_wrapper
class ShowAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(self) -> Any:
        """Generates a visualization of the data model without implements."""
        if self._state.data_model_store.empty:
            raise NeatSessionError("No data model available. Try using [bold].read[/bold] to read a data model.")

        last_target = self._state.data_model_store.provenance[-1].target_entity
        data_model = last_target.conceptual
        analysis = DataModelAnalysis(conceptual=data_model)

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
        data_model = last_target.conceptual
        analysis = DataModelAnalysis(conceptual=data_model)

        di_graph = analysis._conceptual_di_graph(format="implements")
        identifier = to_directory_compatible(str(data_model.metadata.identifier))
        name = f"{identifier}_implements.html"
        return self._generate_visualization(di_graph, name)

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
