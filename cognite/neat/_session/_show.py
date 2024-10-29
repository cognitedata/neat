import random
from typing import Any, cast

import networkx as nx
from ipycytoscape import CytoscapeWidget  # type: ignore
from IPython.display import display

from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules.models.dms._rules import DMSRules
from cognite.neat._rules.models.entities._single_value import ClassEntity, ViewEntity
from cognite.neat._rules.models.information._rules import InformationRules
from cognite.neat._session.exceptions import NeatSessionError
from cognite.neat._utils.rdf_ import remove_namespace_from_uri

from ._state import SessionState


class ShowAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.data_model = ShowDataModelAPI(self._state)
        self.instances = ShowInstanceAPI(self._state)


class ShowInstanceAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(self) -> Any:
        if not self._state.store.graph:
            raise NeatSessionError("No instances available. Try using [bold].read[/bold] to load instances.")

        widget = CytoscapeWidget()
        widget.layout.height = "700px"

        NxGraph, types = self._generate_instance_di_graph_and_types()
        widget_style = self._generate_cytoscape_widget_style(types)
        widget.set_style(widget_style)

        widget.graph.add_graph_from_networkx(NxGraph)
        print("Max of 100 nodes and edges are displayed, which are randomly selected.")

        return display(widget)

    def _generate_instance_di_graph_and_types(self) -> tuple[nx.DiGraph, set[str]]:
        query = """
        SELECT ?s ?p ?o ?ts ?to WHERE {
            ?s ?p ?o .
            FILTER(isIRI(?o))  # Example filter to check if ?o is an IRI (object type)
            FILTER(BOUND(?o))
            FILTER(?p != rdf:type)

            ?s a ?ts .
            ?o a ?to .
        }
        LIMIT 100
        """

        NxGraph = nx.DiGraph()

        types = set()

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

            NxGraph.add_node(subject, label=subject, type=subject_type)
            NxGraph.add_node(object, label=object, type=object_type)
            NxGraph.add_edge(subject, object, label=property_)

            types.add(subject_type)
            types.add(object_type)

        return NxGraph, types

    def _generate_cytoscape_widget_style(self, types: set[str]) -> list[dict]:
        widget_style = [
            {
                "selector": "edge",
                "style": {
                    "width": 1,
                    "target-arrow-shape": "triangle",
                    "curve-style": "bezier",
                    "label": "data(label)",
                    "font-size": "8px",
                    "line-color": "black",
                    "target-arrow-color": "black",
                },
            },
        ]

        colors = self._generate_hex_colors(len(types))

        for i, type_ in enumerate(types):
            widget_style.append(self._generate_node_cytoscape_style(type_, colors[i]))

        return widget_style

    @staticmethod
    def _generate_hex_colors(n: int) -> list[str]:
        """Generate a list of N random HEX color codes."""
        hex_colors = []
        for _ in range(n):
            color = f"#{random.randint(0, 0xFFFFFF):06x}"
            hex_colors.append(color)
        return hex_colors

    @staticmethod
    def _generate_node_cytoscape_style(type_: str, color: str) -> dict:
        template = {
            "css": {
                "content": "data(label)",
                "text-valign": "center",
                "color": "black",
                "font-size": "10px",
                "width": "mapData(score, 0, 1, 10, 50)",
                "height": "mapData(score, 0, 1, 10, 50)",
            },
        }

        template["selector"] = f'node[type = "{type_}"]'  # type: ignore
        template["css"]["background-color"] = color

        return template


class ShowDataModelAPI:
    def __init__(self, state: SessionState) -> None:
        self._state = state

    def __call__(self) -> Any:
        if not self._state.last_verified_dms_rules and not self._state.last_verified_information_rules:
            raise NeatSessionError(
                "No verified data model available. Try using [bold].verify()[/bold] to verify data model."
            )

        if self._state.last_verified_dms_rules:
            NxGraph = self._generate_dms_di_graph()
        elif self._state.last_verified_information_rules:
            NxGraph = self._generate_info_di_graph()

        widget = self._generate_widget()
        widget.graph.add_graph_from_networkx(NxGraph)
        return display(widget)

    def _generate_dms_di_graph(self) -> nx.DiGraph:
        """Generate a DiGraph from the last verified DMS rules."""
        NxGraph = nx.DiGraph()

        # Add nodes and edges from Views sheet
        for view in cast(DMSRules, self._state.last_verified_dms_rules).views:
            # if possible use human readable label coming from the view name
            if not NxGraph.has_node(view.view.suffix):
                NxGraph.add_node(view.view.suffix, label=view.name or view.view.suffix)

            # add implements as edges
            if view.implements:
                for implement in view.implements:
                    if not NxGraph.has_node(implement.suffix):
                        NxGraph.add_node(implement.suffix, label=implement.suffix)

                    NxGraph.add_edge(view.view.suffix, implement.suffix, label="implements")

        # Add nodes and edges from Properties sheet
        for prop_ in cast(DMSRules, self._state.last_verified_dms_rules).properties:
            if prop_.connection and isinstance(prop_.value_type, ViewEntity):
                if not NxGraph.has_node(prop_.view.suffix):
                    NxGraph.add_node(prop_.view.suffix, label=prop_.view.suffix)

                label = f"{prop_.property_} [{0 if prop_.nullable else 1}..{ '' if prop_.is_list else 1}]"
                NxGraph.add_edge(prop_.view.suffix, prop_.value_type.suffix, label=label)

        return NxGraph

    def _generate_info_di_graph(self) -> nx.DiGraph:
        """Generate nodes and edges for the last verified Information rules for DiGraph."""

        NxGraph = nx.DiGraph()

        # Add nodes and edges from Views sheet
        for class_ in cast(InformationRules, self._state.last_verified_information_rules).classes:
            # if possible use human readable label coming from the view name
            if not NxGraph.has_node(class_.class_.suffix):
                NxGraph.add_node(
                    class_.class_.suffix,
                    label=class_.name or class_.class_.suffix,
                )

            # add implements as edges
            if class_.parent:
                for parent in class_.parent:
                    if not NxGraph.has_node(parent.suffix):
                        NxGraph.add_node(parent.suffix, label=parent.suffix)

                    NxGraph.add_edge(class_.class_.suffix, parent.suffix, label="subClassOf")

        # Add nodes and edges from Properties sheet
        for prop_ in cast(InformationRules, self._state.last_verified_information_rules).properties:
            if prop_.type_ == EntityTypes.object_property:
                if not NxGraph.has_node(prop_.class_.suffix):
                    NxGraph.add_node(prop_.class_.suffix, label=prop_.class_.suffix)

                label = f"{prop_.property_} [{1 if prop_.is_mandatory else 0}..{ '' if prop_.is_list else 1}]"
                NxGraph.add_edge(
                    prop_.class_.suffix,
                    cast(ClassEntity, prop_.value_type).suffix,
                    label=label,
                )

        return NxGraph

    def _generate_widget(self):
        """Generates an empty a CytoscapeWidget."""
        widget = CytoscapeWidget()
        widget.layout.height = "700px"

        widget.set_style(
            [
                {
                    "selector": "node",
                    "css": {
                        "content": "data(label)",
                        "text-valign": "center",
                        "color": "black",
                        "background-color": "#33C4FF",
                        "font-size": "10px",
                        "width": "mapData(score, 0, 1, 10, 50)",
                        "height": "mapData(score, 0, 1, 10, 50)",
                    },
                },
                {
                    "selector": "edge",
                    "style": {
                        "width": 1,
                        "target-arrow-shape": "triangle",
                        "curve-style": "bezier",
                        "label": "data(label)",
                        "font-size": "8px",
                        "line-color": "black",
                        "target-arrow-color": "black",
                    },
                },
                {
                    "selector": 'edge[label = "subClassOf"]',
                    "style": {
                        "line-color": "grey",
                        "target-arrow-color": "grey",
                        "line-style": "dashed",
                        "font-size": "8px",
                    },
                },
                {
                    "selector": 'edge[label = "implements"]',
                    "style": {
                        "line-color": "grey",
                        "target-arrow-color": "grey",
                        "line-style": "dashed",
                        "font-size": "8px",
                    },
                },
            ]
        )

        return widget
