import pytest
from pydantic import ValidationError

from cognite.neat._data_model.models.conceptual._concept import Concept
from cognite.neat._data_model.models.entities import ConceptEntity


class TestConcept:
    def test_concept_cannot_implement_itself(self):
        with pytest.raises(ValidationError) as exc_info:
            Concept(
                space="my_space",
                external_id="my_concept",
                version="1.0.0",
                implements=[
                    ConceptEntity(prefix="my_space", suffix="my_concept", version="1.0.0"),
                    ConceptEntity(prefix="other_space", suffix="other_concept"),
                ],
            )
        assert "A concept cannot implement itself" in str(exc_info.value)

    def test_concept_cannot_have_duplicate_implements(self):
        with pytest.raises(ValidationError) as exc_info:
            Concept(
                space="my_space",
                external_id="my_concept",
                implements=[
                    ConceptEntity(prefix="other_space", suffix="other_concept"),
                    ConceptEntity(prefix="other_space", suffix="other_concept"),
                    ConceptEntity(prefix="another_space", suffix="another_concept"),
                ],
            )
        assert "Duplicate concepts found" in str(exc_info.value)
