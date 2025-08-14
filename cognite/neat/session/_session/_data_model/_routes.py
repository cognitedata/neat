from cognite.neat.core._data_model.models.conceptual._verified import ConceptualDataModel
from cognite.neat.core._data_model.models.physical._verified import PhysicalDataModel
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
