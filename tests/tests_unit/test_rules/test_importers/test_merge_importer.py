from cognite.neat.core._rules._shared import ReadRules
from cognite.neat.core._rules.importers import DMSMergeImporter
from cognite.neat.core._rules.importers._base import BaseImporter
from cognite.neat.core._rules.models import DMSInputRules, DMSRules, InformationInputRules
from cognite.neat.core._rules.models.dms import DMSInputContainer, DMSInputMetadata, DMSInputProperty, DMSInputView
from cognite.neat.core._rules.models.information import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
)


class ImportAdditional(BaseImporter):
    def to_rules(self) -> ReadRules[InformationInputRules]:
        return ReadRules(
            rules=InformationInputRules(
                metadata=InformationInputMetadata(
                    external_id="my_model", version="1.0.0", space="neat", creator="doctrino"
                ),
                properties=[
                    InformationInputProperty(
                        "MyAsset",
                        "location",
                        "text",
                        min_count=0,
                        max_count=1,
                    )
                ],
                classes=[
                    InformationInputClass(
                        "MyAsset",
                        implements="CogniteAsset",
                    )
                ],
            ),
            read_context={},
        )


class ImportExisting(BaseImporter):
    def to_rules(self) -> ReadRules[DMSInputRules]:
        return ReadRules(
            rules=DMSInputRules(
                metadata=DMSInputMetadata(external_id="my_model", version="1.0.0", space="neat", creator="doctrino"),
                properties=[
                    DMSInputProperty(
                        "CogniteAsset",
                        "name",
                        "text",
                        min_count=0,
                        max_count=1,
                        container="CogniteDescribable",
                        container_property="name",
                    ),
                    DMSInputProperty(
                        "CogniteEquipment",
                        "name",
                        "text",
                        min_count=0,
                        max_count=1,
                        container="CogniteDescribable",
                        container_property="name",
                    ),
                    DMSInputProperty(
                        "CogniteEquipment",
                        "asset",
                        "CogniteAsset",
                        min_count=0,
                        max_count=10,
                        container="CogniteEquipment",
                        container_property="asset",
                    ),
                ],
                views=[DMSInputView("CogniteAsset"), DMSInputView("CogniteEquipment")],
                containers=[DMSInputContainer("CogniteDescribable"), DMSInputContainer("CogniteEquipment")],
            ),
            read_context={},
        )


class TestMergeImporter:
    def test_merge_importer_happy_path(self) -> None:
        importer = DMSMergeImporter.from_importers(
            existing=ImportExisting(),
            additional=ImportAdditional(),
        )
        input_rules = importer.to_rules()
        assert input_rules.rules is not None
        model = input_rules.rules.as_verified_rules()
        assert isinstance(model, DMSRules)
        assert {view.view.external_id for view in model.views} == {"CogniteAsset", "CogniteEquipment", "MyAsset"}

        assert {(prop.view.external_id, prop.view_property) for prop in model.properties} == {
            ("CogniteAsset", "name"),
            ("CogniteEquipment", "name"),
            ("CogniteEquipment", "asset"),
            ("MyAsset", "location"),
        }
