from pathlib import Path

import pytest
import requests
import yaml
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from tests.config import DATA_FOLDER, DOC_RULES
from tests.data import COGNITE_CORE_ZIP


class TestImportersToYAMLExporter:
    def test_excel_importer_to_yaml(self, deterministic_uuid4: None, data_regression: DataRegressionFixture) -> None:
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
    @pytest.mark.skip("Needs NEAT-608 to be completed")
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

    @pytest.mark.usefixtures("deterministic_uuid4")
    @pytest.mark.freeze_time("2025-01-03")
    def test_to_extension_transformer(self, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(verbose=False)

        neat.read.yaml(COGNITE_CORE_ZIP, format="toolkit")

        neat.verify()

        neat.prepare.data_model.to_enterprise(("sp_enterprise", "Enterprise", "v1"), "Neat", move_connections=True)

        enterprise_yml_str = neat.to.yaml()

        neat.prepare.data_model.to_solution(
            ("sp_solution", "Solution", "v1"),
            "TeamNeat",
            mode="write",
        )

        solution_yml_str = neat.to.yaml()

        neat.prepare.data_model.to_data_product(("sp_data_product", "DataProduct", "v1"), "TeamNeat2")

        data_product_yml_str = neat.to.yaml()

        data_regression.check(
            {
                "enterprise": yaml.safe_load(enterprise_yml_str),
                "solution": yaml.safe_load(solution_yml_str),
                "data_product": yaml.safe_load(data_product_yml_str),
            }
        )
