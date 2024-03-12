import logging
from collections.abc import Iterable
from itertools import islice
from typing import Literal, cast, overload

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import EdgeApply, InstanceApply, NodeApply
from pydantic_core import ErrorDetails

from cognite.neat.exceptions import NeatException
from cognite.neat.graph.stores import NeatGraphStoreBase
from cognite.neat.graph.transformations.query_generator.sparql import triples2dictionary
from cognite.neat.rules.exporter._rules2dms import DMSSchemaComponents
from cognite.neat.rules.exporter._rules2pydantic_models import add_class_prefix_to_xid, rules_to_pydantic_models
from cognite.neat.rules.models.rules import Rules
from cognite.neat.utils.utils import chunker, datetime_utc_now, retry_decorator

from ._base import CogniteLoader


class DMSLoader(CogniteLoader[InstanceApply]):
    """Loads a Neat Graph into CDF as nodes and edges.

    Args:
        rules: Rules object
        graph_store: Graph store
        add_class_prefix: Add class prefix to external_id. Defaults to False.

    """

    def __init__(self, rules: Rules, graph_store: NeatGraphStoreBase, add_class_prefix: bool = False):
        super().__init__(rules, graph_store)
        self.add_class_prefix = add_class_prefix

    @overload
    def load(self, stop_on_exception: Literal[True]) -> Iterable[InstanceApply]:
        ...

    @overload
    def load(self, stop_on_exception: Literal[False] = False) -> Iterable[InstanceApply | ErrorDetails]:
        ...

    def load(self, stop_on_exception: bool = False) -> Iterable[InstanceApply | ErrorDetails]:
        """Load the graph with data."""
        if self.rules.metadata.namespace is None:
            raise ValueError("Namespace is not defined in transformation rules metadata")

        data_model = DMSSchemaComponents.from_rules(self.rules)
        pydantic_models = rules_to_pydantic_models(self.rules)

        exclude = {
            class_name
            for class_name in self.rules.classes
            if f"{self.rules.space}:{class_name}" not in data_model.containers
        }

        for class_name, triples in self._iterate_class_triples(exclude_classes=exclude):
            logging.info(f"<DMSLoader> Processing class : {class_name}")
            counter = 0
            start_time = datetime_utc_now()
            for instance_dict in triples2dictionary(triples).values():
                counter += 1
                try:
                    instance = pydantic_models[class_name].from_dict(instance_dict)  # type: ignore[attr-defined]
                    if self.add_class_prefix:
                        instance.external_id = add_class_prefix_to_xid(
                            class_name=type(instance).__name__, external_id=instance.external_id
                        )
                    new_node = instance.to_node(data_model, self.add_class_prefix)  # type: ignore[attr-defined]
                    is_valid, reason = is_node_valid(new_node)
                    if is_valid:
                        yield new_node
                    else:
                        yield ErrorDetails(
                            input=instance_dict["external_id"],
                            loc=tuple(["Nodes"]),
                            msg=f"Not valid node {new_node.external_id}. Reason: {reason}",
                            type="Node validation error",
                        )
                        continue

                    new_edges = instance.to_edge(data_model, self.add_class_prefix)
                    for new_edge in new_edges:
                        is_valid, reason = is_edge_valid(new_edge)
                        if is_valid:
                            yield new_edge
                        else:
                            yield ErrorDetails(
                                input=instance_dict["external_id"],
                                loc=tuple(["Edges"]),
                                msg=f"Not valid edge {new_edge.external_id}. Reason: {reason}",
                                type="Edge validation error",
                            )
                            continue

                    delta_time = datetime_utc_now() - start_time
                    delta_time = (delta_time.seconds * 1000000 + delta_time.microseconds) / 1000

                except Exception as e:
                    logging.error(
                        f"Instance {instance_dict['external_id']} of {class_name}"
                        f" cannot be resolved to nodes and edges. Reason: {e}"
                    )
                    if stop_on_exception:
                        raise e

                    if isinstance(e, NeatException):
                        yield e.to_error_dict()
                    else:
                        yield ErrorDetails(
                            input=instance_dict["external_id"],
                            loc=tuple(["rdf2nodes_and_edges"]),
                            msg=str(e),
                            type=f"Exception of type {type(e).__name__} occurred  \
                                        when processing instance of {class_name}",
                        )

    def load_to_cdf(
        self, client: CogniteClient, batch_size: int | None = 1000, max_retries: int = 1, retry_delay: int = 3
    ) -> None:
        """Uploads nodes to CDF

        Args:
            client: Instance of CogniteClient
            batch_size: Size of batch. Default to 1000.
            max_retries: Maximum times to retry the upload. Default to 1.
            retry_delay: Time delay before retrying the upload. Default to 3.

        !!! note "batch_size"
            If batch size is set to 1 or None, all nodes will be pushed to CDF in one go.
        """
        if batch_size is None:
            logging.info("Batch size not set, pushing all nodes and edges to CDF in one go!")
            nodes, edges, errors = self.as_nodes_and_edges(stop_on_exception=False)

            @retry_decorator(max_retries=max_retries, retry_delay=retry_delay, component_name="create-instances")
            def create_instances():
                client.data_modeling.instances.apply(
                    nodes=nodes, edges=edges, auto_create_start_nodes=True, auto_create_end_nodes=True
                )

            create_instances()
            return
        logging.info(f"Uploading nodes in batches of {batch_size}")
        for instances in _batched(self.load(stop_on_exception=False), batch_size):
            nodes = [instance for instance in instances if isinstance(instance, NodeApply)]
            edges = [instance for instance in instances if isinstance(instance, EdgeApply)]
            # Todo make _micro_batch_push handle both nodes and edges simultaneously
            _micro_batch_push(
                client, nodes, batch_size, message="Upload", max_retries=max_retries, retry_delay=retry_delay
            )
            _micro_batch_push(
                client, edges, batch_size, message="Upload", max_retries=max_retries, retry_delay=retry_delay
            )

    def as_nodes_and_edges(
        self, stop_on_exception: bool = False
    ) -> tuple[list[NodeApply], list[EdgeApply], list[ErrorDetails]]:
        nodes = []
        edges = []
        exceptions: list[ErrorDetails] = []
        for instance in self.load(stop_on_exception):  # type: ignore[call-overload]
            if isinstance(instance, NodeApply):
                nodes.append(instance)
            elif isinstance(instance, EdgeApply):
                edges.append(instance)
            elif isinstance(instance, dict):
                exceptions.append(cast(ErrorDetails, instance))
            else:
                raise ValueError(f"Unknown instance type: {type(instance)}")
        return nodes, edges, exceptions


def _batched(iterable: Iterable, size: int):
    "Batch data into lists of length n. The last batch may be shorter."
    # batched('ABCDEFG', 3) --> ABC DEF G
    it = iter(iterable)
    while True:
        batch = list(islice(it, size))
        if not batch:
            return
        yield batch


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
