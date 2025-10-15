import pytest
from pydantic import ValidationError

from cognite.neat._data_model.models.conceptual._concept import Concept
from cognite.neat._data_model.models.conceptual._data_model import DataModel


class TestDataModel:
    def test_cannot_have_duplicates_validator_with_duplicates(self) -> None:
        """Test that validator raises error when there are duplicate concepts."""
        concepts = [
            Concept(space="space1", external_id="concept1", version="v1"),
            Concept(space="space1", external_id="concept1", version="v1"),  # Duplicate
            Concept(space="space2", external_id="concept2", version="v2"),
        ]

        with pytest.raises(ValidationError) as exc_info:
            DataModel(space="test_space", external_id="test_model", version="v1", concepts=concepts)

        error_message = str(exc_info.value)
        assert "Duplicate concepts found" in error_message
        assert "space1:concept1(version=v1)" in error_message

    def test_cannot_have_duplicates_validator_multiple_duplicates(self) -> None:
        """Test that validator identifies multiple duplicate concepts."""
        concepts = [
            Concept(space="space1", external_id="concept1", version="v1"),
            Concept(space="space1", external_id="concept1", version="v1"),  # Duplicate
            Concept(space="space2", external_id="concept2", version="v2"),
            Concept(space="space2", external_id="concept2", version="v2"),  # Another duplicate
        ]

        with pytest.raises(ValidationError) as exc_info:
            DataModel(space="test_space", external_id="test_model", version="v1", concepts=concepts)

        error_message = str(exc_info.value)
        assert "Duplicate concepts found" in error_message
        assert "space1:concept1(version=v1)" in error_message
        assert "space2:concept2(version=v2)" in error_message
