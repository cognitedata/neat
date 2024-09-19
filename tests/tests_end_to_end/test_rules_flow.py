from typing import Any

import yaml
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat.rules.exporters import YAMLExporter
from cognite.neat.rules.models.information import InformationInputRules
from cognite.neat.rules.transformers import InformationToDMS, VerifyInformationRules


class TestImportersToYAMLExporter:
    def test_excel_importer_to_yaml(
        self, david_spreadsheet: dict[str, dict[str, Any]], data_regression: DataRegressionFixture
    ) -> None:
        input_rules = InformationInputRules.load(david_spreadsheet)

        verified = VerifyInformationRules(errors="raise").transform(input_rules)

        dms_rules = InformationToDMS().transform(verified)

        yaml_exporter = YAMLExporter()

        exported_yaml_str = yaml_exporter.export(dms_rules.rules)

        exported_rules = yaml.safe_load(exported_yaml_str)

        data_regression.check(exported_rules)
