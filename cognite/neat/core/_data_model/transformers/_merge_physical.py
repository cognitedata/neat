from typing import Literal

from cognite.neat.core._data_model.models import DMSRules
from cognite.neat.core._data_model.models.dms import DMSContainer, DMSProperty, DMSView
from cognite.neat.core._data_model.transformers import VerifiedRulesTransformer


class MergeDMSRules(VerifiedRulesTransformer[DMSRules, DMSRules]):
    """Merges two DMS rules into one.

    Args:
        secondary: The secondary model. The primary model is the one that is passed to the transform method.
        join: The join strategy for merging views. To only keep views from the primary model, use "primary".
            To only keep views from the secondary model, use "secondary". To keep all views, use "combined".
        priority: For properties that exist in both models, the priority determines which model's property is kept.
            For example, if 'name' of a property exists in both models, and the priority is set to "primary",
            the property from the primary model will be kept.
        conflict_resolution: The conflict resolution strategy for merging views. This applies to fields that
            can be combined, such as view.implements. If set to "combine", the implements list will be combined
            to include all implements from both models. If set to "priority", the implements list will be
            given by the 'priority' argument.
    """

    def __init__(
        self,
        secondary: DMSRules,
        join: Literal["primary", "secondary", "combined"] = "combined",
        priority: Literal["primary", "secondary"] = "primary",
        conflict_resolution: Literal["priority", "combine"] = "priority",
    ) -> None:
        self.secondary = secondary
        self.join = join
        self.priority = priority
        self.conflict_resolution = conflict_resolution

    @property
    def description(self) -> str:
        return f"Merged with {self.secondary.metadata.as_data_model_id()}"

    def transform(self, rules: DMSRules) -> DMSRules:
        raise NotImplementedError()

    @classmethod
    def merge_properties(
        cls,
        primary: DMSProperty,
        secondary: DMSProperty,
    ) -> DMSProperty:
        raise NotImplementedError()

    @classmethod
    def merge_views(
        cls,
        primary: DMSView,
        secondary: DMSView,
        conflict_resolution: Literal["priority", "combine"] = "priority",
    ) -> DMSView:
        raise NotImplementedError()

    @classmethod
    def merge_containers(
        cls,
        primary: DMSContainer,
        secondary: DMSContainer,
    ) -> DMSContainer:
        raise NotImplementedError()
