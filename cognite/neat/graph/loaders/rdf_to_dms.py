import logging

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import NodeApply, EdgeApply
from cognite.neat.graph.stores.graph_store import NeatGraphStore
from cognite.neat.rules.exporter.rules2dms import DataModel
from cognite.neat.rules.exporter.rules2pydantic_models import rules_to_pydantic_models
from cognite.neat.rules.models import TransformationRules
from cognite.neat.utils.utils import chunker, datetime_utc_now, retry_decorator


def rdf2nodes_and_edges(
    graph_store: NeatGraphStore,
    transformation_rules: TransformationRules,
    stop_on_exception: bool = False,
) -> tuple[list[NodeApply], list[EdgeApply]]:
    """Generates DMS nodes and edges from knowledge graph stored as RDF triples

    Args:
        graph_store: Instance of NeatGraphStore holding RDF graph
        transformation_rules: Transformation rules holding data model definition
        stop_on_exception: Whether to stop execution on exception. Defaults to False.

    Returns:
        Tuple holding nodes and edges
    """
    data_model = DataModel.from_rules(transformation_rules)
    pydantic_models = rules_to_pydantic_models(transformation_rules)

    nodes = []
    edges = []

    for class_ in transformation_rules.classes:
        if class_ in data_model.containers:
            class_ns = transformation_rules.metadata.namespace[class_]
            class_instance_ids = [
                res[0] for res in graph_store.query(f"SELECT ?instance WHERE {{ ?instance rdf:type <{class_ns}> . }}")
            ]

            for class_instance_id in class_instance_ids:
                try:
                    instance = pydantic_models[class_].from_graph(graph_store, transformation_rules, class_instance_id)
                    nodes.append(instance.to_node(data_model))
                    edges.extend(instance.to_edge(data_model))
                except Exception as e:
                    logging.error(
                        f"Instance {class_instance_id} of {class_} cannot be resolved to nodes and edges. Reason: {e}"
                    )
                    if stop_on_exception:
                        raise e
                    continue

    return nodes, edges


def upload_nodes(
    client: CogniteClient,
    nodes: list[NodeApply],
    batch_size: int = 5000,
    max_retries: int = 1,
    retry_delay: int = 3,
):
    """Uploads nodes to CDF

    Args:
        client: Instance of CogniteClient
        nodes: List of nodes to upload to CDF
        batch_size: Size of batch. Defaults to 5000.
        max_retries: Maximum times to retry the upload. Defaults to 1.
        retry_delay: Time delay before retrying the upload. Defaults to 3.
    """
    if batch_size:
        logging.info(f"Uploading nodes in batches of {batch_size}")
        _micro_batch_push(
            client,
            nodes,
            batch_size,
            push_type="nodes",
            message="Upload",
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

    else:
        logging.info("Batch size not set, pushing all nodes to CDF in one go!")

        @retry_decorator(max_retries=max_retries, retry_delay=retry_delay, component_name="create-nodes")
        def create_nodes():
            client.data_modeling.instances.apply(nodes=nodes, auto_create_start_nodes=True, auto_create_end_nodes=True)

        create_nodes()


def upload_edges(
    client: CogniteClient,
    edges: list[EdgeApply],
    batch_size: int = 5000,
    max_retries: int = 1,
    retry_delay: int = 3,
):
    """Uploads edges to CDF

    Args:
        client: Instance of CogniteClient
        edges: List of edges to upload to CDF
        batch_size: Size of batch. Defaults to 5000.
        max_retries: Maximum times to retry the upload. Defaults to 1.
        retry_delay: Time delay before retrying the upload. Defaults to 3.
    """
    if batch_size:
        logging.info(f"Uploading edges in batches of {batch_size}")
        _micro_batch_push(
            client,
            edges,
            batch_size,
            push_type="edges",
            message="Upload",
            max_retries=max_retries,
            retry_delay=retry_delay,
        )

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
    push_type: str = "nodes",
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

    if push_type not in ["nodes", "edges"]:
        logging.info(f"push_type {push_type} not supported")
        raise ValueError(f"push_type {push_type} not supported")

    for batch in chunker(nodes_or_edges, batch_size):
        counter += len(batch)
        start_time = datetime_utc_now()

        @retry_decorator(max_retries=max_retries, retry_delay=retry_delay, component_name=f"microbatch-{push_type}")
        def upsert_nodes_or_edges(batch):
            if push_type == "nodes":
                client.data_modeling.instances.apply(
                    nodes=nodes_or_edges, auto_create_start_nodes=True, auto_create_end_nodes=True
                )
            elif push_type == "edges":
                client.data_modeling.instances.apply(
                    edges=nodes_or_edges, auto_create_start_nodes=True, auto_create_end_nodes=True
                )

        upsert_nodes_or_edges(batch)

        delta_time = (datetime_utc_now() - start_time).seconds

        msg = f"{message} {counter} of {total} {push_type}, batch processing time: {delta_time:.2f} "
        msg += f"seconds ETC: {delta_time * (total - counter) / (60*batch_size) :.2f} minutes"
        logging.info(msg)
