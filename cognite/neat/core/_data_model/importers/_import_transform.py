from collections.abc import Sequence

from cognite.neat.core._data_model._shared import ReadRules
from cognite.neat.core._data_model.models import UnverifiedConceptualDataModel
from cognite.neat.core._data_model.transformers._base import RulesTransformer
from cognite.neat.core._issues.errors import NeatValueError

from ._base import BaseImporter


class ConceptualTransformImporter(BaseImporter[UnverifiedConceptualDataModel]):
    """Runs a set of transformations after importing a conceptual data model.

    This is useful when importing a data model with classes and properties that do not comply
    with the regex rules for Neat Conceptual Data Model.

    Args:
        importer: The conceptual data model importer.
        transformations: The transformations to run on the imported data model.

    """

    def __init__(
        self,
        importer: BaseImporter[UnverifiedConceptualDataModel],
        transformations: Sequence[
            RulesTransformer[ReadRules[UnverifiedConceptualDataModel], ReadRules[UnverifiedConceptualDataModel]]
        ],
    ) -> None:
        self.importer = importer
        self.transformations = transformations

    @property
    def description(self) -> str:
        return "Imports a data model and runs a set of transformations on it."

    def to_rules(self) -> ReadRules[UnverifiedConceptualDataModel]:
        rules = self.importer.to_rules()
        if not isinstance(rules.rules, UnverifiedConceptualDataModel | None):
            raise NeatValueError(f"Expected UnverifiedConceptualDataModel, got {type(rules.rules)}")
        for transformation in self.transformations:
            rules = transformation.transform(rules)
        return rules
