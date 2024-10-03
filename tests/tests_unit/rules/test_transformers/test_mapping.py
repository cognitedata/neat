from cognite.neat.constants import CLASSIC_CDF_NAMESPACE
from cognite.neat.rules._shared import JustRules
from cognite.neat.rules.models import InformationInputRules
from cognite.neat.rules.models.information import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
)
from cognite.neat.rules.transformers import ClassicToCoreMapper
from cognite.neat.rules.transformers._mapping import ClassMapping, Mapping, PropertyMapping


class TestClassicToCoreMapper:
    def test_map_single_property(self) -> None:
        input_rules = JustRules(
            InformationInputRules(
                metadata=InformationInputMetadata(
                    schema_="partial",
                    prefix="classic",
                    namespace=CLASSIC_CDF_NAMESPACE,
                    version="1.0",
                    creator="neat",
                    data_model_type="enterprise",
                    extension="addition",
                ),
                properties=[
                    InformationInputProperty(
                        class_="Asset",
                        property_="name",
                        value_type="string",
                    )
                ],
                classes=[
                    InformationInputClass(
                        class_="Asset",
                    )
                ],
            )
        )

        mapping = Mapping(
            properties=[
                PropertyMapping(
                    source=InformationInputProperty(
                        class_="Asset",
                        property_="name",
                        value_type="string",
                    ),
                    target=InformationInputProperty(
                        class_="CogniteAsset",
                        property_="name",
                        value_type="string",
                    ),
                )
            ],
            classes=[
                ClassMapping(
                    source=InformationInputClass(
                        class_="Asset",
                    ),
                    target=InformationInputClass(
                        class_="CogniteAsset",
                    ),
                )
            ],
        )

        transformed = ClassicToCoreMapper(mapping).transform(input_rules).rules

        assert transformed.properties == [
            InformationInputProperty(
                class_="CogniteAsset",
                property_="name",
                value_type="string",
                transformation="classic:Asset(classic:name)->cdf-cdm#:CogniteAsset(cdf-cdm#:name)",
            )
        ]
