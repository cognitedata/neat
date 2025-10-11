import contextlib
import io
from pathlib import Path

import pytest
import requests
import yaml
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from tests.v0.config import DOC_RULES
from tests.v0.data import SchemaData


class TestImportersToYAMLExporter:
    def test_excel_importer_to_yaml(self, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(verbose=False)

        neat.read.excel(DOC_RULES / "information-architect-david.xlsx")

        neat.convert()

        exported_yaml_str = neat.to.yaml()

        exported_rules = yaml.safe_load(exported_yaml_str)
        data_regression.check(exported_rules)

    def test_prohibiting_conversion_with_nice_message(self) -> None:
        neat = NeatSession()

        neat.read.rdf.ontology(SchemaData.Conceptual.ontology_with_regex_warnings)

        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            neat.convert()

        printed_statements = output.getvalue()
        assert printed_statements.startswith(
            "[ERROR] Cannot convert: Convert to physical expects conceptual data model"
        )

    @pytest.mark.freeze_time("2017-05-21")
    @pytest.mark.skip("Needs NEAT-608 to be completed")
    def test_ontology_importer_to_yaml(self, data_regression: DataRegressionFixture, tmp_path: Path) -> None:
        neat = NeatSession(verbose=False)

        response = requests.get("https://data.nobelprize.org/terms.rdf")
        tmp_file = tmp_path / "nobelprize.rdf"
        tmp_file.write_bytes(response.content)

        neat.read.rdf(tmp_file, source="Ontology", type="Data Model")
        neat.convert()
        exported_yaml_str = neat.to.yaml()
        exported_rules = yaml.safe_load(exported_yaml_str)
        data_regression.check(exported_rules)

    @pytest.mark.skip("This fails as it is referencing views in CDF that is cannot access without a client")
    @pytest.mark.freeze_time("2017-05-21")
    def test_cdm_extension_verification(self, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(verbose=False)

        neat.read.excel(SchemaData.Physical.isa_plus_cdm_xlsx)

        neat.verify()
        exported_yaml_str = neat.to.yaml()
        exported_rules = yaml.safe_load(exported_yaml_str)
        data_regression.check(exported_rules)
