from cognite.neat.rules.models.information import InformationClass, InformationInputClass, InformationMetadata


class TestBaseRules:
    def test_strip_whitespace_metadata(
        self,
    ) -> None:
        meta = InformationMetadata.model_validate(
            {
                "role": "  information architect  ",
                "dataModelType": "   enterprise   ",
                "schema": "     partial   ",
                "prefix": "  my-prefix  ",
                "namespace": "http://purl.org/cognite/neat/",
                "version": "  0.1.0  ",
                "name": "  My Data Model  ",
                "description": "  My Data Model Description  ",
                "created": "  2022-07-01T00:00:00Z  ",
                "updated": "  2022-07-01T00:00:00Z  ",
                "creator": " Me, Myself, I  ",
            }
        )

        assert meta.prefix == "my-prefix"
        assert meta.schema_ == "partial"
        assert meta.role == "information architect"
        assert meta.data_model_type == "enterprise"
        assert meta.creator == ["Me", "Myself", "I"]

    def test_strip_whitespace_input_class(self) -> None:
        row = InformationInputClass(
            class_="  My Class  ", name="  My Class Name  ", description="  My Class Description  "
        )

        class_ = InformationClass.model_validate(row.dump(default_prefix="neat"))

        assert class_.class_.suffix == "My Class"
        assert class_.name == "My Class Name"
        assert class_.description == "My Class Description"
