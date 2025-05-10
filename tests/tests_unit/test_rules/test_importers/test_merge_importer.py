from collections.abc import Iterable

import pytest

from cognite.neat.core._data_model._shared import InputRules, ReadRules
from cognite.neat.core._data_model.importers import DMSMergeImporter
from cognite.neat.core._data_model.importers._base import BaseImporter
from cognite.neat.core._data_model.models import DMSInputRules, DMSRules, InformationInputRules
from cognite.neat.core._data_model.models.dms import DMSInputContainer, DMSInputMetadata, DMSInputProperty, DMSInputView
from cognite.neat.core._data_model.models.information import (
    InformationInputClass,
    InformationInputMetadata,
    InformationInputProperty,
)
from cognite.neat.core._issues.errors import NeatError


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
                        connection="direct",
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


def merge_importer_unhappy_test_cases() -> Iterable:
    """Test cases for unhappy path of merge importer."""
    yield pytest.param(
        ReadRules(None, {}),
        ReadRules(None, {}),
        "NeatValueError: Cannot merge. Existing data model failed read.",
        id="Missing existing rules",
    )
    yield pytest.param(
        ReadRules(
            DMSInputRules(
                DMSInputMetadata(external_id="my_model", version="1.0.0", creator="doctrino", space="my_space"), [], []
            ),
            {},
        ),
        ReadRules(None, {}),
        "NeatValueError: Cannot merge. Additional data model failed read.",
        id="Missing additional rules",
    )


class TestMergeImporter:
    def test_merge_importer_happy_path(self) -> None:
        importer = DMSMergeImporter(
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

    @pytest.mark.parametrize("existing, additional, expected", list(merge_importer_unhappy_test_cases()))
    def test_merge_importer_unhappy_path(
        self, existing: ReadRules[InputRules], additional: ReadRules[InputRules], expected: str
    ) -> None:
        class DummyExistingFailing(BaseImporter):
            def to_rules(self) -> ReadRules[InputRules]:
                return existing

        class DummyAdditionalFailing(BaseImporter):
            def to_rules(self) -> ReadRules[InputRules]:
                return additional

        # Test with existing rules as None
        with pytest.raises(NeatError) as e:
            DMSMergeImporter(DummyExistingFailing(), DummyAdditionalFailing()).to_rules()
        assert str(e.value) == expected
