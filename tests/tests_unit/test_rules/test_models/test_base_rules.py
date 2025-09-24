from cognite.neat.v0.core._data_model.models.conceptual import (
    Concept,
    ConceptualMetadata,
    UnverifiedConcept,
)


class TestBaseRules:
    def test_strip_whitespace_metadata(
        self,
    ) -> None:
        meta = ConceptualMetadata.model_validate(
            {
                "role": "  information architect  ",
                "space": "  my_space  ",
                "external_id": "  my_external_id  ",
                "version": "  0.1.0  ",
                "name": "  My Data Model  ",
                "description": "  My Data Model Description  ",
                "created": "  2022-07-01T00:00:00Z  ",
                "updated": "  2022-07-01T00:00:00Z  ",
                "creator": " Me, Myself, I  ",
            }
        )

        assert meta.space == "my_space"
        assert meta.external_id == "my_external_id"
        assert meta.role == "information architect"
        assert meta.creator == ["Me", "Myself", "I"]

    def test_strip_whitespace_input_class(self) -> None:
        row = UnverifiedConcept(
            concept="  MyClass  ",
            name="  My Class Name  ",
            description="  My Class Description  ",
        )

        class_ = Concept.model_validate(row.dump(default_prefix="neat"))

        assert class_.concept.suffix == "MyClass"
        assert class_.name == "My Class Name"
        assert class_.description == "My Class Description"
