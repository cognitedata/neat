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
from cognite.neat._utils.io_ import to_directory_compatible
from cognite.neat._utils.rdf_ import remove_namespace_from_uri, uri_display_name

from ._state import SessionState
from .exceptions import session_class_wrapper


@session_class_wrapper
class ShowAPI:
    """Visualise a verified data model or instances contained in the graph store.
    See, for example, `.data_model()` or `.instances()` for more.

    Example:
        Show instances
        ```python
        from cognite.neat import NeatSession
        from cognite.neat import get_cognite_client

        client = get_cognite_client(env_file_path=".env")
        neat = NeatSession(client, storage="oxigraph") # Storage optimised for storage visualisation

        # .... intermediate steps of reading, infering verifying and converting a data model and instances

        neat.show.instances()
        ```

    Example:
        Show data model
        ```python
        neat.show.data_model()
        ```
    """

    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.data_model = ShowDataModelAPI(self._state)
        self.instances = ShowInstanceAPI(self._state)


@session_class_wrapper
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


@session_class_wrapper
class ShowDataModelAPI(ShowBaseAPI):
    """Visualises the verified data model."""

    def __init__(self, state: SessionState) -> None:
        super().__init__(state)
        self._state = state
        self.provenance = ShowDataModelProvenanceAPI(self._state)
        self.implements = ShowDataModelImplementsAPI(self._state)

    def __call__(self) -> Any:
        if not self._state.rule_store.has_verified_rules:
            raise NeatSessionError(
                "No verified data model available. Try using [bold].verify()[/bold] to verify data model."
            )

        rules = self._state.rule_store.last_verified_rule

        if isinstance(rules, DMSRules):
            di_graph = self._generate_dms_di_graph(rules)
        elif isinstance(rules, InformationRules):
            di_graph = self._generate_info_di_graph(rules)
        else:
            # This should never happen, but we need to handle it to satisfy mypy
            raise NeatSessionError(
                f"Unsupported type {type(rules) }. Make sure you have either information or DMS rules."
            )
        identifier = to_directory_compatible(str(rules.metadata.identifier))
        name = f"{identifier}.html"

        return self._generate_visualization(di_graph, name)

    def _generate_dms_di_graph(self, rules: DMSRules) -> nx.DiGraph:
        """Generate a DiGraph from the last verified DMS rules."""
        di_graph = nx.DiGraph()

        # Views with properties or used as ValueType
        # If a view is not used in properties or as ValueType, it is not added to the graph
        # as we typically do not have the properties for it.
        used_views = {prop_.view for prop_ in rules.properties} | {
            prop_.value_type for prop_ in rules.properties if isinstance(prop_.value_type, ViewEntity)
        }

        # Add nodes and edges from Views sheet
        for view in rules.views:
            if view.view not in used_views:
                continue
            # if possible use humanreadable label coming from the view name
            if not di_graph.has_node(view.view.suffix):
                di_graph.add_node(view.view.suffix, label=view.view.suffix)

        # Add nodes and edges from Properties sheet
        for prop_ in rules.properties:
            if prop_.connection and isinstance(prop_.value_type, ViewEntity):
                if not di_graph.has_node(prop_.view.suffix):
                    di_graph.add_node(prop_.view.suffix, label=prop_.view.suffix)
                di_graph.add_edge(
                    prop_.view.suffix,
                    prop_.value_type.suffix,
                    label=prop_.name or prop_.view_property,
                )

        return di_graph

    def _generate_info_di_graph(self, rules: InformationRules) -> nx.DiGraph:
        """Generate DiGraph representing information data model."""

        di_graph = nx.DiGraph()

        # Add nodes and edges from Views sheet
        for class_ in rules.classes:
            # if possible use humanreadable label coming from the view name
            if not di_graph.has_node(class_.class_.suffix):
                di_graph.add_node(
                    class_.class_.suffix,
                    label=class_.name or class_.class_.suffix,
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


@session_class_wrapper
class ShowDataModelImplementsAPI(ShowBaseAPI):
    def __init__(self, state: SessionState) -> None:
        super().__init__(state)
        self._state = state

    def __call__(self) -> Any:
        if not self._state.rule_store.has_verified_rules:
            raise NeatSessionError(
                "No verified data model available. Try using [bold].verify()[/bold] to verify data model."
            )

        rules = self._state.rule_store.last_verified_rule

        if isinstance(rules, DMSRules):
            di_graph = self._generate_dms_di_graph(rules)
        elif isinstance(rules, InformationRules):
            di_graph = self._generate_info_di_graph(rules)
        else:
            # This should never happen, but we need to handle it to satisfy mypy
            raise NeatSessionError(
                f"Unsupported type {type(rules) }. Make sure you have either information or DMS rules."
            )
        identifier = to_directory_compatible(str(rules.metadata.identifier))
        name = f"{identifier}_implements.html"
        return self._generate_visualization(di_graph, name)

    def _generate_dms_di_graph(self, rules: DMSRules) -> nx.DiGraph:
        """Generate a DiGraph from the last verified DMS rules."""
        di_graph = nx.DiGraph()

        # Add nodes and edges from Views sheet
        for view in rules.views:
            # add implements as edges
            if view.implements:
                if not di_graph.has_node(view.view.suffix):
                    di_graph.add_node(view.view.suffix, label=view.view.suffix)
                for implement in view.implements:
                    if not di_graph.has_node(implement.suffix):
                        di_graph.add_node(implement.suffix, label=implement.suffix)

                    di_graph.add_edge(
                        view.view.suffix,
                        implement.suffix,
                        label="implements",
                        dashes=True,
                    )

        return di_graph

    def _generate_info_di_graph(self, rules: InformationRules) -> nx.DiGraph:
        """Generate DiGraph representing information data model."""

        di_graph = nx.DiGraph()

        # Add nodes and edges from Views sheet
        for class_ in rules.classes:
            # if possible use human readable label coming from the view name

            # add subClassOff as edges
            if class_.implements:
                if not di_graph.has_node(class_.class_.suffix):
                    di_graph.add_node(
                        class_.class_.suffix,
                        label=class_.name or class_.class_.suffix,
                    )

                for parent in class_.implements:
                    if not di_graph.has_node(parent.suffix):
                        di_graph.add_node(parent.suffix, label=parent.suffix)
                    di_graph.add_edge(
                        class_.class_.suffix,
                        parent.suffix,
                        label="implements",
                        dashes=True,
                    )

        return di_graph


@session_class_wrapper
class ShowDataModelProvenanceAPI(ShowBaseAPI):
    """Visualises the provenance or steps that have been executed in the NeatSession."""

    def __init__(self, state: SessionState) -> None:
        super().__init__(state)
        self._state = state

    def __call__(self) -> Any:
        if not self._state.rule_store.provenance:
            raise NeatSessionError("No data model available. Try using [bold].read[/bold] to load data model.")

        di_graph = self._generate_dm_provenance_di_graph_and_types()
        unique_hash = self._state.rule_store.calculate_provenance_hash(shorten=True)
        return self._generate_visualization(di_graph, name=f"data_model_provenance_{unique_hash}.html")

    def _generate_dm_provenance_di_graph_and_types(self) -> nx.DiGraph:
        di_graph = nx.DiGraph()
        hex_colored_types = _generate_hex_color_per_type(["Agent", "Entity", "Activity", "Export", "Pruned"])

        for change in self._state.rule_store.provenance:
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

        for source_id, exports in self._state.rule_store.exports_by_source_entity_id.items():
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

        for pruned_lists in self._state.rule_store.pruned_by_source_entity_id.values():
            for prune_path in pruned_lists:
                for change in prune_path:
                    source = uri_display_name(change.source_entity.id_)
                    target = uri_display_name(change.target_entity.id_)
                    di_graph.add_node(
                        target,
                        label=target,
                        type="Pruned",
                        title="Pruned",
                        color=hex_colored_types["Pruned"],
                    )
                    di_graph.add_edge(source, target, label="pruned", color="grey")

        return di_graph


@session_class_wrapper
class ShowInstanceAPI(ShowBaseAPI):
    """Visualise the instances contained in the graph store."""

    def __init__(self, state: SessionState) -> None:
        super().__init__(state)
        self._state = state

    def __call__(self) -> Any:
        if IN_PYODIDE:
            raise NeatSessionError(
                "Instances visualization not available if neat is run in PYODIDE as "
                "PYODIDE dues not support oxigraph storage for NeatSession."
                "Try running neat in regular Jupyter notebook and set [bold]NeatSession(storage='oxigraph')[/bold]."
            )

        if not self._state.instances.store_type == "oxigraph":
            raise NeatSessionError(
                "Visualization is only available for Oxigraph store. "
                'Try setting [bold]NeatSession(storage="oxigraph")[/bold] enable Oxigraph store.'
            )

        if not self._state.instances.store.graph:
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

        types = [type_ for type_, _ in self._state.instances.store.queries.summarize_instances()]
        hex_colored_types = _generate_hex_color_per_type(types)

        for (  # type: ignore
            subject,
            property_,
            object,
            subject_type,
            object_type,
        ) in self._state.instances.store.graph.query(query):
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
