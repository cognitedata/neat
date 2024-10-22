from typing import Literal

from rich.prompt import Prompt

RDFFileType = Literal["Ontology", "IMF Types", "Inference"]
NeatObjectType = Literal["Data Model", "Instances"]


def object_wizard() -> NeatObjectType:
    selection = {str(i + 1): value for i, value in enumerate(NeatObjectType.__args__)}  # type: ignore
    prompt = "Select object:\n" + "\n".join([f"[{key}] {value}" for key, value in selection.items()]) + "\n"
    return selection[Prompt.ask(prompt, choices=list(selection.keys()))]


def rdf_dm_wizard() -> RDFFileType:
    selection = {str(i + 1): value for i, value in enumerate(RDFFileType.__args__)}  # type: ignore
    prompt = "Select source:\n" + "\n".join([f"[{key}] {value}" for key, value in selection.items()]) + "\n"
    return selection[Prompt.ask(prompt, choices=list(selection.keys()))]
