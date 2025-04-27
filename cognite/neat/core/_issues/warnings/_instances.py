from dataclasses import dataclass

from cognite.neat.core._issues import NeatWarning


@dataclass(unsafe_hash=True)
class NoClassFoundWarning(NeatWarning):
    """No class match found for instance {instance}"""

    instance: str


@dataclass(unsafe_hash=True)
class PartialClassFoundWarning(NeatWarning):
    """Instance '{instance}' has no class match with all properties. Best class match is '{best_class}'
    with {missing_count} missing properties: {missing_properties}"""

    instance: str
    best_class: str
    missing_count: int
    missing_properties: frozenset[str]


@dataclass(unsafe_hash=True)
class MultiClassFoundWarning(NeatWarning):
    """Instance '{instance}' has multiple class matching equally well. Selected '{selected_class}', alternatives are
    {alternatives}"""

    instance: str
    selected_class: str
    alternatives: frozenset[str]
