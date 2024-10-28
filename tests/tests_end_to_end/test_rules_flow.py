from tempfile import NamedTemporaryFile

import pytest
import requests
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

    @pytest.mark.freeze_time("2017-05-21")
    def test_ontology_importer_to_yaml(self, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(verbose=False)

        response = requests.get("https://data.nobelprize.org/terms.rdf")
        temp_file = NamedTemporaryFile(delete=False, suffix=".rdf")
        temp_file.write(response.content)

        neat.read.rdf(temp_file.name, source="Ontology", type="Data Model")
        neat.verify()
        neat.convert("dms")
        exported_yaml_str = neat.to.yaml()
        exported_rules = yaml.safe_load(exported_yaml_str)
        data_regression.check(exported_rules)
