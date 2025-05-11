from collections.abc import Sequence

from cognite.neat.core._data_model._shared import ReadRules
from cognite.neat.core._data_model.models import InformationInputRules
from cognite.neat.core._data_model.transformers._base import RulesTransformer
from cognite.neat.core._issues.errors import NeatValueError

from ._base import BaseImporter


class ConceptualTransformImporter(BaseImporter[InformationInputRules]):
    """Runs a set of transformations after importing a conceptual data model.

    This is useful when importing a data model with classes and properties that do not comply
    with the regex rules for Neat Conceptual Data Model.

    Args:
        importer: The conceptual data model importer.
        transformations: The transformations to run on the imported data model.

    """

    def __init__(
        self,
        importer: BaseImporter[InformationInputRules],
        transformations: Sequence[RulesTransformer[ReadRules[InformationInputRules], ReadRules[InformationInputRules]]],
    ) -> None:
        self.importer = importer
        self.transformations = transformations

    @property
    def description(self) -> str:
        return "Imports a data model and runs a set of transformations on it."

    def to_rules(self) -> ReadRules[InformationInputRules]:
        rules = self.importer.to_rules()
        if not isinstance(rules.rules, InformationInputRules | None):
            raise NeatValueError(f"Expected InformationInputRules, got {type(rules.rules)}")
        for transformation in self.transformations:
            rules = transformation.transform(rules)
        return rules
