import yaml
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from tests.config import DOC_RULES


class TestImportersToYAMLExporter:
    def test_excel_importer_to_yaml(self, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(verbose=False)

        neat.read.excel(DOC_RULES / "information-architect-david.xlsx")
        neat.verify()
        neat.convert("dms")
        exported_yaml_str = neat.to.yaml()

        exported_rules = yaml.safe_load(exported_yaml_str)
        data_regression.check(exported_rules)

        exported_rules = yaml.safe_load(exported_yaml_str)

        data_regression.check(exported_rules)
