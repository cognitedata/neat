import logging
from typing import TypeAlias, cast

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import EdgeApply, NodeApply
from pydantic_core import ErrorDetails
from rdflib.term import Node

from cognite.neat.exceptions import NeatException
from cognite.neat.graph.stores.graph_store import NeatGraphStore
from cognite.neat.rules.exporter._rules2dms import DataModel
from cognite.neat.rules.exporter._rules2pydantic_models import add_class_prefix_to_xid, rules_to_pydantic_models
from cognite.neat.rules.models.rules import Rules
from cognite.neat.utils.utils import chunker, datetime_utc_now, retry_decorator

Triple: TypeAlias = tuple[Node, Node, Node]


def rdf2nodes_and_edges(
    graph_store: NeatGraphStore,
    transformation_rules: Rules,
    stop_on_exception: bool = False,
    add_class_prefix: bool = False,
) -> tuple[list[NodeApply], list[EdgeApply], list[ErrorDetails]]:
    """Generates DMS nodes and edges from knowledge graph stored as RDF triples

    Args:
        graph_store: Instance of NeatGraphStore holding RDF graph
        transformation_rules: Transformation rules holding data model definition
        stop_on_exception: Whether to stop execution on exception. Defaults to False.
        add_class_prefix: Whether to add class name as a prefix to instance external id. Defaults to False.

    Returns:
        Tuple holding nodes, edges and exceptions
    """
    if transformation_rules.metadata.namespace is None:
        raise ValueError("Namespace is not defined in transformation rules metadata")

    nodes: list[NodeApply] = []
    edges: list[EdgeApply] = []
    exceptions: list[ErrorDetails] = []

    data_model = DataModel.from_rules(transformation_rules)
    pydantic_models = rules_to_pydantic_models(transformation_rules)

    for class_ in transformation_rules.classes:
        if class_ in data_model.containers:
            class_namespace = transformation_rules.metadata.namespace[class_]
            class_instance_ids = [
                cast(Triple, res)[0]
                for res in graph_store.query(f"SELECT ?instance WHERE {{ ?instance rdf:type <{class_namespace}> . }}")
            ]

            counter = 0
            start_time = datetime_utc_now()
            total = len(class_instance_ids)

            for class_instance_id in class_instance_ids:
                counter += 1
                try:
                    instance = pydantic_models[class_].from_graph(  # type: ignore[attr-defined]
                        graph_store, transformation_rules, class_instance_id
                    )
                    if add_class_prefix:
                        instance.external_id = add_class_prefix_to_xid(
                            class_name=instance.__class__.__name__, external_id=instance.external_id
                        )
                    new_node = instance.to_node(data_model, add_class_prefix)
                    is_valid, reason = is_node_valid(new_node)
                    if not is_valid:
                        exceptions.append(
                            ErrorDetails(
                                input=class_instance_id,
                                loc=tuple(["Nodes"]),
                                msg=f"Not valid node {new_node.external_id}. Reason: {reason}",
                                type="Node validation error",
                            )
                        )
                        continue
                    nodes.append(new_node)

                    new_edges = instance.to_edge(data_model, add_class_prefix)
                    for new_edge in new_edges:
                        is_valid, reason = is_edge_valid(new_edge)
                        if not is_valid:
                            exceptions.append(
                                ErrorDetails(
                                    input=class_instance_id,
                                    loc=tuple(["Edges"]),
                                    msg=f"Not valid edge {new_edge.external_id}. Reason: {reason}",
                                    type="Edge validation error",
                                )
                            )
                            continue
                        edges.append(new_edge)

                    delta_time = datetime_utc_now() - start_time
                    delta_time = (delta_time.seconds * 1000000 + delta_time.microseconds) / 1000
                    msg = (
                        f"{class_} {counter} of {total} instances processed, "
                        f"instance processing time: {delta_time/counter:.2f} "
                    )
                    msg += f"ms ETC: {(delta_time/counter) * (total - counter) / 1000 :.3f} s"
                    logging.info(msg)

                except Exception as e:
                    logging.error(
                        f"Instance {class_instance_id} of {class_} cannot be resolved to nodes and edges. Reason: {e}"
                    )
                    if stop_on_exception:
                        raise e

                    if isinstance(e, NeatException):
                        exceptions.append(e.to_error_dict())
                    else:
                        exceptions.append(
                            ErrorDetails(
                                input=class_instance_id,
                                loc=tuple(["rdf2nodes_and_edges"]),
                                msg=str(e),
                                type=f"Exception of type {type(e).__name__} occurred  \
                                when processing instance of {class_}",
                            )
                        )
                    continue

    return nodes, edges, exceptions


def is_node_valid(node: NodeApply) -> tuple[bool, str]:
    return is_valid_external_id(node.external_id)


def is_edge_valid(edge: EdgeApply) -> tuple[bool, str]:
    for external_id in [edge.external_id, edge.start_node.external_id, edge.end_node.external_id]:
        is_valid, reason = is_valid_external_id(external_id)
        if not is_valid:
            return False, reason
    return True, ""


def is_valid_external_id(external_id: str) -> tuple[bool, str]:
    if external_id is None or external_id == "" or len(external_id) >= 255:
        return False, f"external_id {external_id} is empty of too long"
    return True, ""


def upload_nodes(
    client: CogniteClient, nodes: list[NodeApply], batch_size: int = 1000, max_retries: int = 1, retry_delay: int = 3
):
    """Uploads nodes to CDF

    Args:
        client: Instance of CogniteClient
        nodes: List of nodes to upload to CDF
        batch_size: Size of batch. Defaults to 1000.
        max_retries: Maximum times to retry the upload. Defaults to 1.
        retry_delay: Time delay before retrying the upload. Defaults to 3.

    !!! note "batch_size"
        If batch size is set to 1 or None, all nodes will be pushed to CDF in one go.
    """
    if batch_size:
        logging.info(f"Uploading nodes in batches of {batch_size}")
        _micro_batch_push(client, nodes, batch_size, message="Upload", max_retries=max_retries, retry_delay=retry_delay)

    else:
        logging.info("Batch size not set, pushing all nodes to CDF in one go!")

        @retry_decorator(max_retries=max_retries, retry_delay=retry_delay, component_name="create-nodes")
        def create_nodes():
            client.data_modeling.instances.apply(nodes=nodes)

        create_nodes()


def upload_edges(
    client: CogniteClient, edges: list[EdgeApply], batch_size: int = 5000, max_retries: int = 1, retry_delay: int = 3
):
    """Uploads edges to CDF

    Args:
        client: Instance of CogniteClient
        edges: List of edges to upload to CDF
        batch_size: Size of batch. Defaults to 5000.
        max_retries: Maximum times to retry the upload. Defaults to 1.
        retry_delay: Time delay before retrying the upload. Defaults to 3.

    !!! note "batch_size"
        If batch size is set to 1 or None, all edges will be pushed to CDF in one go.

    """
    if batch_size:
        logging.info(f"Uploading edges in batches of {batch_size}")
        _micro_batch_push(client, edges, batch_size, message="Upload", max_retries=max_retries, retry_delay=retry_delay)

    else:
        logging.info("Batch size not set, pushing all edges to CDF in one go!")

        @retry_decorator(max_retries=max_retries, retry_delay=retry_delay, component_name="create-edges")
        def create_nodes():
            client.data_modeling.instances.apply(edges=edges, auto_create_start_nodes=True, auto_create_end_nodes=True)

        create_nodes()


def _micro_batch_push(
    client: CogniteClient,
    nodes_or_edges: list[NodeApply] | list[EdgeApply],
    batch_size: int = 1000,
    message: str = "Upload",
    max_retries: int = 1,
    retry_delay: int = 3,
):
    """Uploads nodes or edges in batches

    Args:
        client: Instance of CogniteClient
        nodes_or_edges: List of nodes or edges
        batch_size: Size of batch. Defaults to 1000.
        push_type: Type of push, either "nodes" or "edges". Defaults to "nodes".
        message: Message to logged. Defaults to "Upload".
        max_retries: Maximum times to retry the upload. Defaults to 1.
        retry_delay: Time delay before retrying the upload. Defaults to 3.
    """
    total = len(nodes_or_edges)
    counter = 0

    if nodes_or_edges and isinstance(nodes_or_edges[0], NodeApply):
        push_type = "nodes"
    elif nodes_or_edges and isinstance(nodes_or_edges[0], EdgeApply):
        push_type = "edges"
    else:
        raise ValueError("nodes_or_edges must be a list of NodeApply or EdgeApply objects")

    for batch in chunker(nodes_or_edges, batch_size):
        counter += len(batch)
        start_time = datetime_utc_now()

        @retry_decorator(max_retries=max_retries, retry_delay=retry_delay, component_name=f"microbatch-{push_type}")
        def upsert_nodes_or_edges(upload_batch):
            if push_type == "nodes":
                client.data_modeling.instances.apply(nodes=upload_batch)
            elif push_type == "edges":
                client.data_modeling.instances.apply(
                    edges=upload_batch, auto_create_start_nodes=True, auto_create_end_nodes=True
                )

        upsert_nodes_or_edges(batch)

        delta_time = (datetime_utc_now() - start_time).seconds

        msg = f"{message} {counter} of {total} {push_type}, batch processing time: {delta_time:.2f} "
        msg += f"seconds ETC: {delta_time * (total - counter) / (60*batch_size) :.2f} minutes"
        logging.info(msg)
