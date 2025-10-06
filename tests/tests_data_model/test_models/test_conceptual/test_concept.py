from typing import cast

import pytest
from pydantic import ValidationError

from cognite.neat._data_model.models.conceptual._concept import Concept
from cognite.neat._data_model.models.entities import ConceptEntity


class TestConcept:
    def test_happy_path_simple_concept(self) -> None:
        concept = Concept(space="my_space", external_id="my_concept", version="1.0.0")
        assert concept.space == "my_space"
        assert concept.external_id == "my_concept"
        assert concept.version == "1.0.0"
        assert concept.implements is None

    def test_happy_path_simple_concept_empty_list_of_implements(self) -> None:
        concept = Concept(space="my_space", external_id="my_concept", version="1.0.0", implements=[])
        assert concept.space == "my_space"
        assert concept.external_id == "my_concept"
        assert concept.version == "1.0.0"
        assert concept.implements == []

    def test_happy_path_concept_with_implements(self) -> None:
        concept = Concept(
            space="my_space",
            external_id="my_concept",
            version="1.0.0",
            implements=[
                ConceptEntity(prefix="other_space", suffix="other_concept"),
                ConceptEntity(prefix="another_space", suffix="another_concept", version="2.0.0"),
            ],
        )
        assert concept.space == "my_space"
        assert concept.external_id == "my_concept"
        assert concept.version == "1.0.0"
        assert len(cast(list[ConceptEntity], concept.implements)) == 2
        assert cast(list[ConceptEntity], concept.implements)[0].prefix == "other_space"
        assert cast(list[ConceptEntity], concept.implements)[0].suffix == "other_concept"
        assert cast(list[ConceptEntity], concept.implements)[0].version is None
        assert cast(list[ConceptEntity], concept.implements)[1].prefix == "another_space"
        assert cast(list[ConceptEntity], concept.implements)[1].suffix == "another_concept"
        assert cast(list[ConceptEntity], concept.implements)[1].version == "2.0.0"

    def test_concept_cannot_implement_itself(self) -> None:
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

    def test_concept_cannot_have_duplicate_implements(self) -> None:
        with pytest.raises(ValidationError) as exc_info:
            Concept(
                space="my_space",
                external_id="my_concept",
                implements=[
                    ConceptEntity(prefix="other_space", suffix="other_concept"),
                    ConceptEntity(prefix="other_space", suffix="other_concept"),
                    ConceptEntity(prefix="another_space", suffix="another_concept"),
                    ConceptEntity(prefix="another_space", suffix="another_concept"),
                ],
            )
        assert "Duplicate concepts found: another_space:another_concept and other_space:other_concept" in str(
            exc_info.value
        )
