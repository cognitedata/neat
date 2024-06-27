import hashlib
import logging
import re
import sys
import time
from collections import Counter, OrderedDict
from collections.abc import Iterable
from datetime import datetime
from functools import wraps
from typing import TypeAlias, cast, overload

import pandas as pd
from cognite.client import ClientConfig, CogniteClient
from cognite.client.credentials import CredentialProvider, OAuthClientCredentials, OAuthInteractive, Token
from cognite.client.exceptions import CogniteDuplicatedError, CogniteReadTimeout
from pydantic import HttpUrl, TypeAdapter, ValidationError
from pydantic_core import ErrorDetails
from pyparsing import Any
from rdflib import Literal, Namespace
from rdflib.term import URIRef

from cognite.neat import _version
from cognite.neat.utils.cdf import CogniteClientConfig, InteractiveCogniteClient, ServiceCogniteClient

if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    from datetime import timezone

    UTC = timezone.utc


Triple: TypeAlias = tuple[URIRef, URIRef, Literal | URIRef]


def get_cognite_client_from_config(config: ServiceCogniteClient) -> CogniteClient:
    credentials = OAuthClientCredentials(
        token_url=config.token_url, client_id=config.client_id, client_secret=config.client_secret, scopes=config.scopes
    )

    return _get_cognite_client(config, credentials)


def get_cognite_client_from_token(config: ServiceCogniteClient) -> CogniteClient:
    credentials = Token(config.client_secret)
    return _get_cognite_client(config, credentials)


def get_cognite_client_interactive(config: InteractiveCogniteClient) -> CogniteClient:
    credentials = OAuthInteractive(
        authority_url=config.authority_url,
        client_id=config.client_id,
        scopes=config.scopes,
        redirect_port=config.redirect_port,
    )
    return _get_cognite_client(config, credentials)


def _get_cognite_client(config: CogniteClientConfig, credentials: CredentialProvider) -> CogniteClient:
    logging.info(f"Creating CogniteClient with parameters : {config}")

    # The client name is used for aggregated logging of Neat Usage
    client_name = f"CogniteNeat:{_version.__version__}"
    return CogniteClient(
        ClientConfig(
            client_name=client_name,
            base_url=config.base_url,
            project=config.project,
            credentials=credentials,
            timeout=config.timeout,
            max_workers=config.max_workers,
            debug=False,
        )
    )


@overload
def remove_namespace(*URI: URIRef | str, special_separator: str = "#_") -> str: ...


@overload
def remove_namespace(*URI: tuple[URIRef | str, ...], special_separator: str = "#_") -> tuple[str, ...]: ...


def remove_namespace(
    *URI: URIRef | str | tuple[URIRef | str, ...], special_separator: str = "#_"
) -> tuple[str, ...] | str:
    """Removes namespace from URI

    Args
        URI: URIRef | str
            URI of an entity
        special_separator : str
            Special separator to use instead of # or / if present in URI
            Set by default to "#_" which covers special client use case

    Returns
        Entities id without namespace

    Examples:

        >>> remove_namespace("http://www.example.org/index.html#section2")
        'section2'
        >>> remove_namespace("http://www.example.org/index.html#section2", "http://www.example.org/index.html#section3")
        ('section2', 'section3')
    """
    if isinstance(URI, str | URIRef):
        uris = (URI,)
    elif isinstance(URI, tuple):
        # Assume that all elements in the tuple are of the same type following type hint
        uris = cast(tuple[URIRef | str, ...], URI)
    else:
        raise TypeError(f"URI must be of type URIRef or str, got {type(URI)}")

    output = []
    for u in uris:
        try:
            _ = TypeAdapter(HttpUrl).validate_python(u)
            output.append(u.split(special_separator if special_separator in u else "#" if "#" in u else "/")[-1])
        except ValidationError:
            output.append(str(u))

    return tuple(output) if len(output) > 1 else output[0]


def get_namespace(URI: URIRef, special_separator: str = "#_") -> str:
    """Removes namespace from URI

    Parameters
    ----------
    URI : URIRef
        URI of an entity
    special_separator : str
        Special separator to use instead of # or / if present in URI
        Set by default to "#_" which covers special client use case

    Returns
    -------
    str
        Entity id without namespace
    """
    if special_separator in URI:
        return URI.split(special_separator)[0] + special_separator
    elif "#" in URI:
        return URI.split("#")[0] + "#"
    else:
        return "/".join(URI.split("/")[:-1]) + "/"


def as_neat_compliant_uri(uri: URIRef) -> URIRef:
    namespace = get_namespace(uri)
    id_ = remove_namespace(uri)
    compliant_uri = re.sub(r"[^a-zA-Z0-9-_.]", "", id_)
    return URIRef(f"{namespace}{compliant_uri}")


def convert_rdflib_content(content: Literal | URIRef | dict | list) -> Any:
    if isinstance(content, Literal) or isinstance(content, URIRef):
        return content.toPython()
    elif isinstance(content, dict):
        return {key: convert_rdflib_content(value) for key, value in content.items()}
    elif isinstance(content, list):
        return [convert_rdflib_content(item) for item in content]
    else:
        return content


def uri_to_short_form(URI: URIRef, prefixes: dict[str, Namespace]) -> str | URIRef:
    """Returns the short form of a URI if its namespace is present in the prefixes dict,
    otherwise returns the URI itself

    Args:
        URI: URI to be converted to form prefix:entityName
        prefixes: dict of prefixes

    Returns:
        shortest form of the URI if its namespace is present in the prefixes dict,
        otherwise returns the URI itself
    """
    uris: set[str | URIRef] = {URI}
    for prefix, namespace in prefixes.items():
        if URI.startswith(namespace):
            uris.add(f"{prefix}:{URI.replace(namespace, '')}")
    return min(uris, key=len)


def _traverse(hierarchy: dict, graph: dict, names: list[str]) -> dict:
    """traverse the graph and return the hierarchy"""
    for name in names:
        hierarchy[name] = _traverse({}, graph, graph[name])
    return hierarchy


def get_generation_order(
    class_linkage: pd.DataFrame, parent_col: str = "source_class", child_col: str = "target_class"
) -> dict:
    parent_child_list = class_linkage[[parent_col, child_col]].values.tolist()
    # Build a directed graph and a list of all names that have no parent
    graph: dict[str, set[str]] = {name: set() for tup in parent_child_list for name in tup}
    has_parent = {name: False for tup in parent_child_list for name in tup}
    for parent, child in parent_child_list:
        graph[parent].add(child)
        has_parent[child] = True

    # All names that have absolutely no parent:
    roots = [name for name, parents in has_parent.items() if not parents]

    return _traverse({}, graph, roots)


def prettify_generation_order(generation_order: dict, depth: dict | None = None, start=-1) -> dict:
    """Prettifies generation order dictionary for easier consumption."""
    depth = depth or {}
    for key, value in generation_order.items():
        depth[key] = start + 1
        if isinstance(value, dict):
            prettify_generation_order(value, depth, start=start + 1)
    return OrderedDict(sorted(depth.items(), key=lambda item: item[1]))


def epoch_now_ms() -> int:
    return int((datetime.now(UTC) - datetime(1970, 1, 1, tzinfo=UTC)).total_seconds() * 1000)


def chunker(sequence, chunk_size):
    return [sequence[i : i + chunk_size] for i in range(0, len(sequence), chunk_size)]


def datetime_utc_now():
    return datetime.now(UTC)


def retry_decorator(max_retries=2, retry_delay=3, component_name=""):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            previous_exception = None
            for attempt in range(max_retries + 1):
                try:
                    logging.debug(f"Attempt {attempt + 1} of {max_retries + 1} for {component_name}")
                    return func(*args, **kwargs)
                except CogniteReadTimeout as e:
                    previous_exception = e
                    if attempt < max_retries:
                        logging.error(
                            f"""CogniteReadTimeout retry attempt {attempt + 1} failed for {component_name} .
                            Retrying in {retry_delay} second(s). Error:"""
                        )
                        logging.error(e)
                        time.sleep(retry_delay)
                    else:
                        raise e
                except CogniteDuplicatedError as e:
                    if isinstance(previous_exception, CogniteReadTimeout):
                        # if previous exception was CogniteReadTimeout,
                        # we can't be sure if the items were created or not
                        if len(e.successful) == 0 and len(e.failed) == 0 and len(e.duplicated) >= 0:
                            logging.warning(
                                f"Duplicate error for {component_name} . All items already exist in CDF. "
                                "Suppressing error."
                            )
                            return
                        else:
                            # can happend because of eventual consistency. Retry with delay to allow for CDF to catch up
                            if attempt < max_retries:
                                logging.error(
                                    f"""CogniteDuplicatedError retry attempt {attempt + 1} failed for {component_name} .
                                      Retrying in {retry_delay} second(s). Error:"""
                                )
                                logging.error(e)
                                # incerasing delay to allow for CDF to catch up
                                time.sleep(retry_delay)
                            else:
                                raise e
                    else:
                        # no point in retrying duplicate error if previous exception was not a timeout
                        raise e

                except Exception as e:
                    previous_exception = e
                    if attempt < max_retries:
                        logging.error(
                            f"Retry attempt {attempt + 1} failed for {component_name}. "
                            f"Retrying in {retry_delay} second(s)."
                        )
                        logging.error(e)
                        time.sleep(retry_delay)
                    else:
                        raise e

        return wrapper

    return decorator


def create_sha256_hash(string: str) -> str:
    # Create a SHA-256 hash object
    sha256_hash = hashlib.sha256()

    # Convert the string to bytes and update the hash object
    sha256_hash.update(string.encode("utf-8"))

    # Get the hexadecimal representation of the hash
    hash_value = sha256_hash.hexdigest()

    return hash_value


def generate_exception_report(exceptions: list[dict] | list[ErrorDetails] | None, category: str = "") -> str:
    exceptions_as_dict = _order_expectations_by_type(exceptions) if exceptions else {}
    report = ""

    for exception_type in exceptions_as_dict.keys():
        title = f"# {category}: {exception_type}" if category else ""
        warnings = "\n- " + "\n- ".join(exceptions_as_dict[exception_type])
        report += title + warnings + "\n\n"

    return report


def _order_expectations_by_type(exceptions: list[dict] | list[ErrorDetails]) -> dict[str, list[str]]:
    exception_dict: dict[str, list[str]] = {}
    for exception in exceptions:
        if not isinstance(exception["loc"], str) and isinstance(exception["loc"], Iterable):
            location = f"[{'/'.join(str(e) for e in exception['loc'])}]"
        else:
            location = ""

        issue = f"{exception['msg']} {location}"

        if exception_dict.get(exception["type"]) is None:
            exception_dict[exception["type"]] = [issue]
        else:
            exception_dict[exception["type"]].append(issue)
    return exception_dict


def remove_none_elements_from_set(s):
    return {x for x in s if x is not None}


def get_inheritance_path(child: Any, child_parent: dict[Any, list[Any]]) -> list:
    """Returns the inheritance path for a given child

    Args:
        child: Child class
        child_parent: Dictionary of child to parent relationship

    Returns:
        Inheritance path for a given child

    !!! note "No Circular Inheritance"
        This method assumes that the child_parent dictionary is a tree and does not contain any cycles.
    """
    path = []
    if child in child_parent:
        path.extend(child_parent[child])
        for parent in child_parent[child]:
            path.extend(get_inheritance_path(parent, child_parent))
    return path


def replace_non_alphanumeric_with_underscore(text):
    return re.sub(r"\W+", "_", text)


def string_to_ideal_type(input_string: str) -> int | bool | float | datetime | str:
    try:
        # Try converting to int
        return int(input_string)
    except ValueError:
        try:
            # Try converting to float
            return float(input_string)  # type: ignore
        except ValueError:
            if input_string.lower() == "true":
                # Return True if input is 'true'
                return True
            elif input_string.lower() == "false":
                # Return False if input is 'false'
                return False
            else:
                try:
                    # Try converting to datetime
                    return datetime.fromisoformat(input_string)  # type: ignore
                except ValueError:
                    # Return the input string if no conversion is possible
                    return input_string


def most_occurring_element(list_of_elements: list):
    counts = Counter(list_of_elements)
    return counts.most_common(1)[0][0]
