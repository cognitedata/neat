from abc import ABC
from typing import cast

from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._data_model._shared import (
    ImportedDataModel,
    T_ImportedUnverifiedDataModel,
    T_VerifiedDataModel,
    VerifiedDataModel,
)
from cognite.neat.v0.core._data_model.models import (
    ConceptualDataModel,
    PhysicalDataModel,
    UnverifiedConceptualDataModel,
    UnverifiedPhysicalDataModel,
)
from cognite.neat.v0.core._data_model.models.conceptual import ConceptualValidation
from cognite.neat.v0.core._data_model.models.physical import PhysicalValidation
from cognite.neat.v0.core._issues import MultiValueError, catch_issues
from cognite.neat.v0.core._issues.errors import NeatTypeError, NeatValueError

from ._base import DataModelTransformer


class VerificationTransformer(DataModelTransformer[T_ImportedUnverifiedDataModel, T_VerifiedDataModel], ABC):
    """Base class for all verification transformers."""

    _data_model_cls: type[T_VerifiedDataModel]
    _validation_cls: type

    def __init__(self, validate: bool = True, client: NeatClient | None = None) -> None:
        self.validate = validate
        self._client = client

    def transform(self, data_model: T_ImportedUnverifiedDataModel) -> T_VerifiedDataModel:
        in_ = data_model.unverified_data_model
        if in_ is None:
            raise NeatValueError("Cannot verify data model. The reading of the data model failed.")
        verified_data_model: T_VerifiedDataModel | None = None
        # We need to catch issues as we use the error args to provide extra context for the errors/warnings
        # For example, which row in the spreadsheet the error occurred.
        with catch_issues(data_model.context) as issues:
            data_model_cls = self._get_data_model_cls(data_model)
            dumped = in_.dump()
            verified_data_model = data_model_cls.model_validate(dumped)  # type: ignore[assignment]
            if self.validate:
                validation_cls = self._get_validation_cls(verified_data_model)  # type: ignore[arg-type]
                if issubclass(validation_cls, PhysicalValidation):
                    validation_issues = PhysicalValidation(
                        cast(PhysicalDataModel, verified_data_model),
                        self._client,
                        data_model.context,
                    ).validate()  # type: ignore[arg-type]
                elif issubclass(validation_cls, ConceptualValidation):
                    validation_issues = ConceptualValidation(verified_data_model, data_model.context).validate()  # type: ignore[arg-type]
                else:
                    raise NeatValueError("Unsupported data model type")
                issues.extend(validation_issues)

        # Raise issues which is expected to be handled outside of this method
        issues.trigger_warnings()
        if issues.has_errors:
            raise MultiValueError(issues.errors)
        if verified_data_model is None:
            raise NeatValueError("Data model was not verified")
        return verified_data_model

    def _get_data_model_cls(self, in_: T_ImportedUnverifiedDataModel) -> type[T_VerifiedDataModel]:
        return self._data_model_cls

    def _get_validation_cls(self, data_model: T_VerifiedDataModel) -> type:
        return self._validation_cls

    @property
    def description(self) -> str:
        return "Verify data model"


class VerifyPhysicalDataModel(
    VerificationTransformer[ImportedDataModel[UnverifiedPhysicalDataModel], PhysicalDataModel]
):
    """Class to verify physical data model."""

    _data_model_cls = PhysicalDataModel
    _validation_cls = PhysicalValidation

    def transform(self, data_model: ImportedDataModel[UnverifiedPhysicalDataModel]) -> PhysicalDataModel:
        return super().transform(data_model)


class VerifyConceptualDataModel(
    VerificationTransformer[ImportedDataModel[UnverifiedConceptualDataModel], ConceptualDataModel]
):
    """Class to verify conceptual data model."""

    _data_model_cls = ConceptualDataModel
    _validation_cls = ConceptualValidation

    def transform(self, data_model: ImportedDataModel[UnverifiedConceptualDataModel]) -> ConceptualDataModel:
        return super().transform(data_model)


class VerifyAnyDataModel(VerificationTransformer[T_ImportedUnverifiedDataModel, VerifiedDataModel]):
    """Class to verify arbitrary data model"""

    def _get_data_model_cls(self, in_: T_ImportedUnverifiedDataModel) -> type[VerifiedDataModel]:
        if isinstance(in_.unverified_data_model, UnverifiedConceptualDataModel):
            return ConceptualDataModel
        elif isinstance(in_.unverified_data_model, UnverifiedPhysicalDataModel):
            return PhysicalDataModel
        else:
            raise NeatTypeError(f"Unsupported data model type: {type(in_)}")

    def _get_validation_cls(self, data_model: VerifiedDataModel) -> type:
        if isinstance(data_model, ConceptualDataModel):
            return ConceptualValidation
        elif isinstance(data_model, PhysicalDataModel):
            return PhysicalValidation
        else:
            raise NeatTypeError(f"Unsupported data model type: {type(data_model)}")
