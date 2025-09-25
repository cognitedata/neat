import hashlib
import importlib
import inspect
import logging
import time
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from types import ModuleType
from typing import Any

from cognite.client.exceptions import CogniteDuplicatedError, CogniteReadTimeout

from cognite.neat.v0.core._issues.errors._general import NeatImportError


def local_import(module: str, extra: str) -> ModuleType:
    try:
        return importlib.import_module(module)
    except ImportError as e:
        raise NeatImportError(module.split(".")[0], extra) from e


def get_classmethods(cls: type) -> list[Callable]:
    return [
        func for _, func in inspect.getmembers(cls, lambda x: inspect.ismethod(x) and not x.__name__.startswith("_"))
    ]


def class_html_doc(cls: type, include_factory_methods: bool = True) -> str:
    if cls.__doc__:
        docstring = cls.__doc__.split("Args:")[0].strip().replace("\n", "<br />")
    else:
        docstring = "Missing Description"
    if include_factory_methods:
        factory_methods = get_classmethods(cls)
        if factory_methods:
            factory_methods_str = "".join(f"<li><em>.{m.__name__}</em></li>" for m in factory_methods)
            docstring += (
                f"<br /><strong>Available factory methods:</strong><br />"
                f'<ul style="list-style-type:circle;">{factory_methods_str}</ul>'
            )
    return f"<h3>{cls.__name__}</h3><p>{docstring}</p>"


def retry_decorator(max_retries: int = 2, retry_delay: int = 3, component_name: str = "") -> Any:
    def decorator(func: Callable) -> Any:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
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
                    # Deliberately ignoring here, this should be refactored.
                    previous_exception = e  # type: ignore
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


def get_parameters_by_method(obj: object, prefix: str = "") -> dict[str, dict[str, type]]:
    annotation_by_method = {}
    namespace_dict = {**dict(obj.__class__.__dict__.items()), **vars(obj)}
    for name, value in namespace_dict.items():
        if name != "__call__" and (name.startswith("_") or isinstance(value, property)):
            continue
        if callable(value) and type(value).__name__ == "function":
            annotation_by_method[f"{prefix}{name}"] = get_parameters(value)
        elif isinstance(value, object) and type(value).__module__ != "builtins":
            sub_prefix = f"{prefix}{name}." if prefix else f"{name}."
            annotation_by_method.update(get_parameters_by_method(value, sub_prefix))
    return annotation_by_method


def get_parameters(obj: Callable) -> dict[str, type]:
    annotations = inspect.get_annotations(obj)
    return {name: annotations[name] for name in annotations if name != "return"}


def filter_kwargs_by_method(kwargs: dict[str, Any], method: Callable) -> dict[str, Any]:
    """Filter kwargs by method parameters."""
    signature = inspect.signature(method)
    return {k: v for k, v in kwargs.items() if k in signature.parameters}
