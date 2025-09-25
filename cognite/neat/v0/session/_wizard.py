from collections.abc import Sequence
from typing import Literal, TypeVar, get_args

from rich.prompt import IntPrompt, Prompt

from cognite.neat.v0.core._data_model._constants import PATTERNS

RDFFileType = Literal["Ontology", "IMF Types", "Inference"]
NeatObjectType = Literal["Data Model", "Instances"]
XMLFileType = Literal["dexpi", "aml"]


def object_wizard(message: str = "Select object") -> NeatObjectType:
    return _selection(message, get_args(NeatObjectType))


def xml_format_wizard(message: str = "Select XML format") -> XMLFileType:
    return _selection(message, get_args(XMLFileType))


def rdf_dm_wizard(message: str = "Select source:") -> RDFFileType:
    return _selection(message, get_args(RDFFileType))


_T_Option = TypeVar("_T_Option")


def _selection(message: str, options: Sequence[_T_Option]) -> _T_Option:
    option_text = "\n  ".join([f"{i + 1}) {option}" for i, option in enumerate(options)])
    selected_index = (
        IntPrompt().ask(f"{message}\n  {option_text}\n", choices=list(map(str, range(1, len(options) + 1)))) - 1
    )
    return options[selected_index]


def space_wizard(message: str = "Set space", space: str | None = None) -> str:
    while True:
        user_input = space or Prompt().ask(f"{message}:")
        if PATTERNS.space_compliance.match(str(user_input)):
            return user_input
        else:
            print(f"Invalid input. Please provide a valid space name. {PATTERNS.space_compliance.pattern}")

        space = ""
