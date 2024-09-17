from cognite.neat.rules.models.information import InformationMetadata


class TestBaseRules:
    def test_strip_whitespace(
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
