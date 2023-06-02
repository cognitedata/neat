import logging
import time
from collections import OrderedDict
from datetime import datetime, timezone
from functools import wraps

import pandas as pd
from cognite.client import ClientConfig, CogniteClient
from cognite.client.credentials import CredentialProvider, OAuthClientCredentials, OAuthInteractive
from rdflib.term import URIRef

from cognite.neat.core.data_classes.config import InteractiveClient, ServiceClient
from cognite.neat.core.loader.graph_store import NeatGraphStore


def get_cognite_client_from_config(config: ServiceClient) -> CogniteClient:
    credentials = OAuthClientCredentials(
        token_url=config.token_url, client_id=config.client_id, client_secret=config.client_secret, scopes=config.scopes
    )

    return _get_cognite_client(config, credentials)


def get_cognite_client_interactive(config: InteractiveClient) -> CogniteClient:
    credentials = OAuthInteractive(
        authority_url=config.authority_url,
        client_id=config.client_id,
        scopes=config.scopes,
        redirect_port=config.redirect_port,
    )
    return _get_cognite_client(config, credentials)


def _get_cognite_client(config: ClientConfig, credentials: CredentialProvider) -> CogniteClient:
    return CogniteClient(
        ClientConfig(
            client_name=config.client_name,
            base_url=config.base_url,
            project=config.project,
            credentials=credentials,
            timeout=60,
            max_workers=3,
            debug=False,
        )
    )


def add_triples(graph_store: NeatGraphStore, triples: list[tuple], batch_size: int = 10000):
    """Adds triples to the graph store in batches.

    Parameters
    ----------
    graph_store : NeatGraphStore
        Instance of NeatGraphStore
    triples : list[tuple]
        list of triples to be added to the graph store
    batch_size : int, optional
        Batch size of triples per commit, by default 10000
    """

    commit_counter = 0
    logging.info(f"Committing total of {len(triples)} triples to knowledge graph!")
    total_number_of_triples = len(triples)
    number_of_uploaded_triples = 0

    def check_commit(force_commit: bool = False):
        """Commit nodes to the graph if batch counter is reached or if force_commit is True"""
        nonlocal commit_counter
        nonlocal number_of_uploaded_triples
        if force_commit:
            number_of_uploaded_triples += commit_counter
            graph_store.graph.commit()
            logging.info(f"Committed {number_of_uploaded_triples} of {total_number_of_triples} triples")
            return
        commit_counter += 1
        if commit_counter >= batch_size:
            number_of_uploaded_triples += commit_counter
            graph_store.graph.commit()
            logging.info(f"Committed {number_of_uploaded_triples} of {total_number_of_triples} triples")
            commit_counter = 0

    for triple in triples:
        graph_store.graph.add(triple)
        check_commit()

    check_commit(force_commit=True)


def remove_namespace(URI: URIRef, special_separator: str = "#_") -> str:
    """Removes namespace from URI

    Parameters
    ----------
    URI : URIRef
        URI of an entity
    special_separator : str
        Special separator to use instead of # or / if present in URI
        Set by default to "#_" which covers Statnett use case

    Returns
    -------
    str
        Entity id without namespace
    """

    return URI.split(special_separator if special_separator in URI else ("#" if "#" in URI else "/"))[-1]


def _traverse(hierarchy: dict, graph: dict, names: str) -> dict:
    """traverse the graph and return the hierarchy"""
    for name in names:
        hierarchy[name] = _traverse({}, graph, graph[name])
    return hierarchy


def get_generation_order(
    class_linkage: pd.DataFrame, parent_col: str = "source_class", child_col: str = "target_class"
) -> dict:
    parent_child_list = class_linkage[[parent_col, child_col]].values.tolist()
    # Build a directed graph and a list of all names that have no parent
    graph = {name: set() for tup in parent_child_list for name in tup}
    has_parent = {name: False for tup in parent_child_list for name in tup}
    for parent, child in parent_child_list:
        graph[parent].add(child)
        has_parent[child] = True

    # All names that have absolutely no parent:
    roots = [name for name, parents in has_parent.items() if not parents]

    return _traverse({}, graph, roots)


def prettify_generation_order(generation_order: dict, depth: dict = None, start=-1) -> dict:
    """Prettifies generation order dictionary for easier consumption."""
    depth = depth or {}
    for key, value in generation_order.items():
        depth[key] = start + 1
        if isinstance(value, dict):
            prettify_generation_order(value, depth, start=start + 1)
    return OrderedDict(sorted(depth.items(), key=lambda item: item[1]))


def epoch_now_ms():
    return int((datetime.now(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds() * 1000)


def chunker(sequence, chunk_size):
    return [sequence[i : i + chunk_size] for i in range(0, len(sequence), chunk_size)]


def datetime_utc_now():
    return datetime.now(timezone.utc)


def retry_decorator(max_retries=2, retry_delay=3, component_name=""):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    logging.debug(f"Attempt {attempt + 1} of {max_retries + 1} for {component_name}")
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries:
                        logging.error(
                            f"Retry attempt {attempt + 1} failed for {component_name} . Retrying in {retry_delay} second(s)."
                        )
                        logging.error(e)
                        time.sleep(retry_delay)
                    else:
                        raise e

        return wrapper

    return decorator
