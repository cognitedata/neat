from pathlib import Path

import pytest
import requests
import yaml
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from tests.config import DATA_FOLDER, DOC_RULES


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
    def test_ontology_importer_to_yaml(self, data_regression: DataRegressionFixture, tmp_path: Path) -> None:
        neat = NeatSession(verbose=False)

        response = requests.get("https://data.nobelprize.org/terms.rdf")
        tmp_file = tmp_path / "nobelprize.rdf"
        tmp_file.write_bytes(response.content)

        neat.read.rdf(tmp_file, source="Ontology", type="Data Model")
        neat.verify()
        neat.convert("dms")
        exported_yaml_str = neat.to.yaml()
        exported_rules = yaml.safe_load(exported_yaml_str)
        data_regression.check(exported_rules)

    @pytest.mark.skip("This fails as it is referencing views in CDF that is cannot access without a client")
    @pytest.mark.freeze_time("2017-05-21")
    def test_cdm_extension_verification(self, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(verbose=False)

        neat.read.excel(DATA_FOLDER / "isa_plus_cdm.xlsx")

        neat.verify()

        exported_yaml_str = neat.to.yaml()
        exported_rules = yaml.safe_load(exported_yaml_str)
        data_regression.check(exported_rules)

    @pytest.mark.freeze_time("2024-11-22")
    def test_read_model_to_data_product(self, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(verbose=False)

        neat.read.excel(DOC_RULES / "cdf-dms-architect-alice.xlsx")

        neat.verify()

        neat.prepare.data_model.to_data_product(("my_space", "MyProduct", "v1"), org_name="")

        exported_yaml_str = neat.to.yaml()
        exported_rules = yaml.safe_load(exported_yaml_str)
        data_regression.check(exported_rules)
