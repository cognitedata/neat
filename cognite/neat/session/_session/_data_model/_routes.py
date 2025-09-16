from typing import Literal

from cognite.client import data_modeling as dm

from cognite.neat.core._data_model import importers
from cognite.neat.core._data_model.models.conceptual._verified import ConceptualDataModel
from cognite.neat.core._data_model.models.physical._verified import PhysicalDataModel
from cognite.neat.core._data_model.transformers._converters import (
    ConceptualToPhysical,
    MergeConceptualDataModels,
    MergePhysicalDataModels,
    ToDMSCompliantEntities,
)
from cognite.neat.core._data_model.transformers._verification import VerifyConceptualDataModel
from cognite.neat.core._issues._base import IssueList
from cognite.neat.core._issues.errors._general import RegexViolationError
from cognite.neat.core._store._data_model import DataModelEntity
from cognite.neat.session._session._data_model._read import ReadAPI
from cognite.neat.session._session._data_model._show import ShowAPI
from cognite.neat.session._session._data_model._write import WriteAPI
from cognite.neat.session._state import SessionState
from cognite.neat.session.exceptions import session_class_wrapper


@session_class_wrapper
class DataModelAPI:
    """API for managing data models in NEAT session."""

    def __init__(self, state: SessionState) -> None:
        self._state = state
        self.read = ReadAPI(state)
        self.write = WriteAPI(state)
        self.show = ShowAPI(state)

    @property
    def physical(self) -> PhysicalDataModel | None:
        """Access to the physical data model level."""
        return self._state.data_model_store.try_get_last_physical_data_model

    @property
    def conceptual(self) -> ConceptualDataModel | None:
        """Access to the conceptual data model level."""
        return self._state.data_model_store.try_get_last_conceptual_data_model

    def _repr_html_(self) -> str:
        if self._state.data_model_store.empty:
            return (
                "<strong>No data model</strong>. Get started by reading data model with the <em>.read</em> attribute."
            )

        output = []

        if self._state.data_model_store.provenance:
            if self.physical:
                html = self.physical._repr_html_()
            if self.conceptual:
                html = self.conceptual._repr_html_()
            output.append(f"<H2>Data Model</H2><br />{html}")

        return "<br />".join(output)

    def convert(self, reserved_properties: Literal["error", "warning"] = "warning") -> IssueList:
        """Converts the last verified conceptual data model to the physical data model.

        Args:
            reserved_properties: What to do with reserved properties. Can be "error" or "warning".

        Example:
            Convert to Physical Data Model
            ```python
            neat.data_model.convert()
            ```
        """
        self._state._raise_exception_if_condition_not_met(
            "Convert to physical",
            has_physical_data_model=False,
            has_conceptual_data_model=True,
            can_convert_to_physical_data_model=True,
        )
        converter = ConceptualToPhysical(reserved_properties=reserved_properties, client=self._state.client)

        issues = self._state.data_model_transform(converter)

        if issues.has_errors:
            print("Conversion failed.")
        if issues:
            print("You can inspect the issues with the .inspect.issues(...) method.")
            if issues.has_error_type(RegexViolationError):
                print("You can use .prepare. to try to fix the issues")

        return issues

    def infer(
        self,
        model_id: dm.DataModelId | tuple[str, str, str] = (
            "neat_space",
            "NeatInferredDataModel",
            "v1",
        ),
    ) -> IssueList:
        """Data model inference from instances.

        Args:
            model_id: The ID of the inferred data model.

        Example:
            Infer a data model after reading a source file
            ```python
            # From an active NeatSession
            ...
            neat.read.xml.dexpi("url_or_path_to_dexpi_file")
            neat.infer()
            ```
        """
        self._state._raise_exception_if_condition_not_met("Data model inference", instances_required=True)
        return self._infer_subclasses(model_id)

    def _infer_subclasses(
        self,
        model_id: dm.DataModelId | tuple[str, str, str] = (
            "neat_space",
            "NeatInferredDataModel",
            "v1",
        ),
    ) -> IssueList:
        """Infer data model from instances."""
        last_entity: DataModelEntity | None = None
        if self._state.data_model_store.provenance:
            last_entity = self._state.data_model_store.provenance[-1].target_entity

        # Note that this importer behaves as a transformer in the data model store when there
        # is an existing data model.
        # We are essentially transforming the last entity's conceptual data model
        # into a new conceptual data model.
        importer = importers.SubclassInferenceImporter(
            issue_list=IssueList(),
            graph=self._state.instances.store.graph(),
            data_model=last_entity.conceptual if last_entity is not None else None,
            data_model_id=(dm.DataModelId.load(model_id) if last_entity is None else None),
        )

        def action() -> tuple[ConceptualDataModel, PhysicalDataModel | None]:
            unverified_conceptual = importer.to_data_model()
            unverified_conceptual = ToDMSCompliantEntities(rename_warning="raise").transform(unverified_conceptual)

            extra_conceptual = VerifyConceptualDataModel().transform(unverified_conceptual)
            if not last_entity:
                return extra_conceptual, None
            merged_conceptual = MergeConceptualDataModels(extra_conceptual).transform(last_entity.conceptual)
            if not last_entity.physical:
                return merged_conceptual, None

            extra_physical = ConceptualToPhysical(reserved_properties="warning", client=self._state.client).transform(
                extra_conceptual
            )

            merged_physical = MergePhysicalDataModels(extra_physical).transform(last_entity.physical)
            return merged_conceptual, merged_physical

        return self._state.data_model_store.do_activity(action, importer)
