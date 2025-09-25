import yaml

from cognite.neat import NeatSession
from cognite.neat.v0.core._data_model.catalog import classic_model
from cognite.neat.v0.core._instances.extractors import AssetsExtractor
from tests.v0.data import InstanceData


class TestSubInferenceImporter:
    def test_infer_metadata(self) -> None:
        neat = NeatSession()
        neat._state.instances.store.write(
            AssetsExtractor(
                InstanceData.classic_windfarm.ASSETS,
                unpack_metadata=True,
                as_write=True,
                prefix="Classic",
            )
        )
        neat.read.excel(classic_model)
        issues = neat.infer()
        assert len(issues) == 0

        rules_yaml = neat.to.yaml()
        rules = yaml.safe_load(rules_yaml)
        expected_metadata_properties = {
            "assetCategory",
            "height",
            "turbineType",
            "maxCapacity",
        }
        actual_properties = {prop["property_"] for prop in rules["properties"] if prop["concept"] == "ClassicAsset"}
        assert expected_metadata_properties <= actual_properties
