from typing import Any

import networkx as nx
from IPython.display import HTML, display
from pyvis.network import Network as PyVisNetwork  # type: ignore

from cognite.neat.core._constants import IN_NOTEBOOK, IN_PYODIDE
from cognite.neat.core._data_model.analysis._base import DataModelAnalysis
from cognite.neat.core._utils.io_ import to_directory_compatible
from cognite.neat.core._utils.rdf_ import uri_display_name
from cognite.neat.session._show import _generate_hex_color_per_type
from cognite.neat.session._state import SessionState
from cognite.neat.session.exceptions import NeatSessionError, session_class_wrapper


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
