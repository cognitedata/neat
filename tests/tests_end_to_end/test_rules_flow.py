from pathlib import Path

import pytest
import requests
import yaml
from cognite.client.data_classes.data_modeling import (
    Container,
    ContainerApply,
    ContainerId,
    ContainerList,
)
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat import NeatSession
from cognite.neat._client.data_classes.schema import DMSSchema
from cognite.neat._client.testing import monkeypatch_neat_client
from tests.config import DATA_FOLDER, DOC_RULES
from tests.data import COGNITE_CORE_ZIP


class TestImportersToYAMLExporter:
    def test_excel_importer_to_yaml(self, data_regression: DataRegressionFixture) -> None:
        neat = NeatSession(verbose=False)

        neat.read.excel(DOC_RULES / "information-architect-david.xlsx")

        neat.convert()

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
        neat.convert()
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

    @pytest.mark.freeze_time("2025-01-03")
    def test_to_extension_transformer(
        self, cognite_core_schema: DMSSchema, data_regression: DataRegressionFixture
    ) -> None:
        def lookup_containers(ids: list[ContainerId]) -> ContainerList:
            return ContainerList(
                [
                    as_container_read(cognite_core_schema.containers[container_id])
                    for container_id in ids
                    if container_id in cognite_core_schema.containers
                ]
            )

        def pickup_containers(container: list[ContainerApply]) -> ContainerList:
            for item in container:
                container_id = item.as_id()
                if container_id not in cognite_core_schema.containers:
                    cognite_core_schema.containers[container_id] = item
            return ContainerList([as_container_read(item) for item in container])

        with monkeypatch_neat_client() as client:
            # In the data product, we need to be able to look up the containers
            client.data_modeling.containers.retrieve.side_effect = lookup_containers
            client.data_modeling.containers.apply.side_effect = pickup_containers

            neat = NeatSession(client, verbose=False)

            neat.read.yaml(COGNITE_CORE_ZIP, format="toolkit")

            neat.verify()

            neat.create.enterprise_model(("sp_enterprise", "Enterprise", "v1"), "Neat")

            enterprise_yml_str = neat.to.yaml()

            # Writing to CDF such that the mock client can look up the containers in the data product step.
            neat.to.cdf.data_model()

            neat.create.solution_model(("sp_solution", "Solution", "v1"))

            solution_yml_str = neat.to.yaml()

            neat.create.data_product_model(("sp_data_product", "DataProduct", "v1"))

            data_product_yml_str = neat.to.yaml()

        data_regression.check(
            {
                "enterprise": yaml.safe_load(enterprise_yml_str),
                "solution": yaml.safe_load(solution_yml_str),
                "data_product": yaml.safe_load(data_product_yml_str),
            }
        )


def as_container_read(container: ContainerApply) -> Container:
    return Container.load(
        {
            **container.dump(),
            "isGlobal": True,
            "lastUpdatedTime": 1,
            "createdTime": 0,
        }
    )
