from abc import ABC
from collections.abc import Iterable

import pytest

from cognite.neat.v0.core._constants import CLASSIC_CDF_NAMESPACE
from cognite.neat.v0.core._data_model._shared import ImportedDataModel
from cognite.neat.v0.core._data_model.models import (
    ConceptualDataModel,
    PhysicalDataModel,
    UnverifiedConceptualDataModel,
    UnverifiedPhysicalDataModel,
)
from cognite.neat.v0.core._data_model.transformers import (
    AddCogniteProperties,
    AddConceptImplements,
    ClassicPrepareCore,
    DataModelTransformer,
    DropModelViews,
    IncludeReferenced,
    PhysicalDataModelMapper,
    PrefixEntities,
    SetIDDMSModel,
    ToExtensionModel,
)

TRANSFORMATION_CLASSES = list(DataModelTransformer.__subclasses__())


def instantiated_transformers_cls() -> Iterable[DataModelTransformer]:
    for transformation_cls in TRANSFORMATION_CLASSES:
        if ABC in transformation_cls.__bases__:
            continue
        if issubclass(transformation_cls, PrefixEntities):
            yield transformation_cls(prefix="test")
        elif issubclass(transformation_cls, SetIDDMSModel | ToExtensionModel):
            yield transformation_cls(("my_space", "my_id", "v1"))
        elif issubclass(transformation_cls, DropModelViews):
            yield transformation_cls("3D")
        elif issubclass(transformation_cls, AddConceptImplements):
            yield transformation_cls("Edge", "Edge")
        elif issubclass(
            transformation_cls,
            PhysicalDataModelMapper | IncludeReferenced | AddCogniteProperties,
        ):
            # Manually checked as these require NeatClient or DMSRules in the setup
            continue
        elif issubclass(transformation_cls, ClassicPrepareCore):
            return ClassicPrepareCore(CLASSIC_CDF_NAMESPACE)
        else:
            yield transformation_cls()


class TestRuleTransformer:
    @pytest.mark.parametrize("transformer_cls", TRANSFORMATION_CLASSES)
    def test_transform_method_valid_signature(self, transformer_cls: type[DataModelTransformer]) -> None:
        valid_type_hints = {
            PhysicalDataModel,
            ConceptualDataModel,
            ImportedDataModel[UnverifiedConceptualDataModel],
            ImportedDataModel[UnverifiedPhysicalDataModel],
        }

        type_hint = transformer_cls.transform_type_hint()

        invalid_type_hints = set(type_hint) - valid_type_hints

        assert not invalid_type_hints, f"Invalid type hints: {invalid_type_hints}"

    @pytest.mark.parametrize(
        "transformer", [pytest.param(v, id=type(v).__name__) for v in instantiated_transformers_cls()]
    )
    def test_has_description(self, transformer: DataModelTransformer) -> None:
        assert transformer.description != "MISSING DESCRIPTION", f"Missing description for {transformer}"
