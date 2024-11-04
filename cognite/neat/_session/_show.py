import colorsys
import random
from typing import Any, cast

import networkx as nx
from IPython.display import HTML, display
from pyvis.network import Network as PyVisNetwork  # type: ignore

from cognite.neat._constants import IN_NOTEBOOK, IN_PYODIDE
from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.models.dms._rules import DMSRules
from cognite.neat._rules.models.entities._single_value import ClassEntity, ViewEntity
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._session.exceptions import NeatSessionError
from cognite.neat._utils.rdf_ import remove_namespace_from_uri

from ._state import SessionState
from .exceptions import intercept_session_exceptions


@intercept_session_exceptions
class ShowAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.data_model = ShowDataModelAPI(self._state)
        self.instances = ShowInstanceAPI(self._state)


@intercept_session_exceptions
class ShowBaseAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

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


@intercept_session_exceptions
class ShowDataModelAPI(ShowBaseAPI):
    def __init__(self, state: SessionState) -> None:
        super().__init__(state)
        self._state = state

    def __call__(self) -> Any:
        if not self._state.has_verified_rules:
            raise NeatSessionError(
                "No verified data model available. Try using [bold].verify()[/bold] to verify data model."
            )

        try:
            di_graph = self._generate_dms_di_graph(self._state.last_verified_dms_rules)
            name = "dms_data_model.html"
        except NeatSessionError:
            di_graph = self._generate_info_di_graph(self._state.last_verified_information_rules)
            name = "information_data_model.html"

        return self._generate_visualization(di_graph, name)

    def _generate_dms_di_graph(self, rules: DMSRules) -> nx.DiGraph:
        """Generate a DiGraph from the last verified DMS rules."""
        di_graph = nx.DiGraph()

        # Add nodes and edges from Views sheet
        for view in rules.views:
            # if possible use human readable label coming from the view name
            if not di_graph.has_node(view.view.suffix):
                di_graph.add_node(view.view.suffix, label=view.name or view.view.suffix)

            # add implements as edges
            if view.implements:
                for implement in view.implements:
                    if not di_graph.has_node(implement.suffix):
                        di_graph.add_node(implement.suffix, label=implement.suffix)

                    di_graph.add_edge(
                        view.view.suffix,
                        implement.suffix,
                        label="implements",
                        dashes=True,
                    )

        # Add nodes and edges from Properties sheet
        for prop_ in rules.properties:
            if prop_.connection and isinstance(prop_.value_type, ViewEntity):
                if not di_graph.has_node(prop_.view.suffix):
                    di_graph.add_node(prop_.view.suffix, label=prop_.view.suffix)
                di_graph.add_edge(
                    prop_.view.suffix,
                    prop_.value_type.suffix,
                    label=prop_.name or prop_.property_,
                )

        return di_graph

    def _generate_info_di_graph(self, rules: InformationRules) -> nx.DiGraph:
        """Generate DiGraph representing information data model."""

        di_graph = nx.DiGraph()

        # Add nodes and edges from Views sheet
        for class_ in rules.classes:
            # if possible use human readable label coming from the view name
            if not di_graph.has_node(class_.class_.suffix):
                di_graph.add_node(
                    class_.class_.suffix,
                    label=class_.name or class_.class_.suffix,
                )

            # add subClassOff as edges
            if class_.parent:
                for parent in class_.parent:
                    if not di_graph.has_node(parent.suffix):
                        di_graph.add_node(parent.suffix, label=parent.suffix)
                    di_graph.add_edge(
                        class_.class_.suffix,
                        parent.suffix,
                        label="subClassOf",
                        dashes=True,
                    )

        # Add nodes and edges from Properties sheet
        for prop_ in rules.properties:
            if prop_.type_ == EntityTypes.object_property:
                if not di_graph.has_node(prop_.class_.suffix):
                    di_graph.add_node(prop_.class_.suffix, label=prop_.class_.suffix)

                di_graph.add_edge(
                    prop_.class_.suffix,
                    cast(ClassEntity, prop_.value_type).suffix,
                    label=prop_.name or prop_.property_,
                )

        return di_graph


@intercept_session_exceptions
class ShowInstanceAPI(ShowBaseAPI):
    def __init__(self, state: SessionState) -> None:
        super().__init__(state)
        self._state = state

    def __call__(self) -> Any:
        if not self._state.store.graph:
            raise NeatSessionError("No instances available. Try using [bold].read[/bold] to load instances.")

        di_graph = self._generate_instance_di_graph_and_types()
        return self._generate_visualization(di_graph, name="instances.html")

    def _generate_instance_di_graph_and_types(self) -> nx.DiGraph:
        query = """
        SELECT ?s ?p ?o ?ts ?to WHERE {
            ?s ?p ?o .
            FILTER(isIRI(?o))  # Example filter to check if ?o is an IRI (object type)
            FILTER(BOUND(?o))
            FILTER(?p != rdf:type)

            ?s a ?ts .
            ?o a ?to .
        }
        LIMIT 200
        """

        di_graph = nx.DiGraph()

        types = [type_ for type_, _ in self._state.store.queries.summarize_instances()]
        hex_colored_types = self._generate_hex_color_per_type(types)

        for (  # type: ignore
            subject,
            property_,
            object,
            subject_type,
            object_type,
        ) in self._state.store.graph.query(query):
            subject = remove_namespace_from_uri(subject)
            property_ = remove_namespace_from_uri(property_)
            object = remove_namespace_from_uri(object)
            subject_type = remove_namespace_from_uri(subject_type)
            object_type = remove_namespace_from_uri(object_type)

            di_graph.add_node(
                subject,
                label=subject,
                type=subject_type,
                title=subject_type,
                color=hex_colored_types[subject_type],
            )
            di_graph.add_node(
                object,
                label=object,
                type=object_type,
                title=object_type,
                color=hex_colored_types[object_type],
            )
            di_graph.add_edge(subject, object, label=property_, color="grey")

        return di_graph

    @staticmethod
    def _generate_hex_color_per_type(types: list[str]) -> dict:
        hex_colored_types = {}
        random.seed(381)
        for type_ in types:
            hue = random.random()
            saturation = random.uniform(0.5, 1.0)
            lightness = random.uniform(0.4, 0.6)
            rgb = colorsys.hls_to_rgb(hue, lightness, saturation)
            hex_color = f"#{int(rgb[0] * 255):02x}{int(rgb[1] * 255):02x}{int(rgb[2] * 255):02x}"
            hex_colored_types[type_] = hex_color
        return hex_colored_types
