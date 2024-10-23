from collections.abc import Sequence
from typing import Literal, get_args, TypeVar

from rich.prompt import IntPrompt

RDFFileType = Literal["Ontology", "IMF Types", "Inference"]
NeatObjectType = Literal["Data Model", "Instances"]


def object_wizard(message: str = "Select object") -> NeatObjectType:
    return _selection(message, get_args(NeatObjectType))


def rdf_dm_wizard(message: str = "Select source:") -> RDFFileType:
    return _selection(message, get_args(RDFFileType))


_T_Option = TypeVar("_T_Option")

def _selection(message: str, options: Sequence[_T_Option]) -> _T_Option:
    option_text = "\n  ".join([f"{i+1}) {option}" for i, option in enumerate(options)])
    selected_index = IntPrompt().ask(f"{message}\n  {option_text}\n", choices=list(map(str,range(1, len(options) + 1)))) -1
    return options[selected_index]

