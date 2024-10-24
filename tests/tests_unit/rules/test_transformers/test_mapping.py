from cognite.neat._constants import CLASSIC_CDF_NAMESPACE
from cognite.neat._rules._shared import JustRules
from cognite.neat._rules.models import InformationInputRules
from cognite.neat._rules.models._base_rules import ClassRef, PropertyRef
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._rules.models.information import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
)
from cognite.neat._rules.models.mapping import Mapping, MappingList, RuleMapping
from cognite.neat._rules.transformers import RuleMapper


class TestClassicToCoreMapper:
    def test_map_single_property(self) -> None:
        classic = "classic"
        core = "core"
        input_ = InformationInputRules(
            metadata=InformationInputMetadata(
                schema_="partial",
                prefix=classic,
                namespace=CLASSIC_CDF_NAMESPACE,
                version="1.0",
                creator="neat",
                data_model_type="enterprise",
                extension="addition",
                name="TheClassic",
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
        ).as_rules()

        input_rules = JustRules(input_)

        mapping = RuleMapping(
            properties=MappingList[PropertyRef](
                [
                    Mapping[PropertyRef](
                        source=PropertyRef(
                            Class=ClassEntity.load(f"{classic}:Asset"),
                            Property="name",
                        ),
                        destination=PropertyRef(
                            Class=ClassEntity.load(f"{core}:CogniteAsset"),
                            Property="name",
                        ),
                    )
                ]
            ),
            classes=MappingList[ClassRef](
                [
                    Mapping[ClassRef](
                        source=ClassRef(Class=ClassEntity.load(f"{classic}:Asset")),
                        destination=ClassRef(Class=ClassEntity.load(f"{core}:CogniteAsset")),
                    )
                ]
            ),
        )

        transformed = RuleMapper(mapping).transform(input_rules).rules

        assert len(transformed.properties) == 1
        prop = transformed.properties[0]
        assert prop.class_ == ClassEntity.load(f"{core}:CogniteAsset")
        assert prop.property_ == "name"

        assert len(transformed.classes) == 1
        cls_ = transformed.classes[0]
        assert cls_.class_ == ClassEntity.load(f"{core}:CogniteAsset")
