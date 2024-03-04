from cognite.neat.rules.importers import DTDLImporter
from cognite.neat.rules.models._rules import InformationRules
from tests.tests_unit.rules.test_importers.constants import DTDL_IMPORTER_DATA


class TestDTDLImporter:
    def test_import_energy_grid_example(self) -> None:
        dtdl_importer = DTDLImporter.from_directory(DTDL_IMPORTER_DATA / "energy_grid")

        rules = dtdl_importer.to_rules(errors="raise")

        assert isinstance(rules, InformationRules)
