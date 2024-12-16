import yaml
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat._rules import catalog, exporters, importers, transformers
from cognite.neat._store import NeatRulesStore


class TestRuleStore:
    def test_write_transform_read(self, data_regression: DataRegressionFixture) -> None:
        store = NeatRulesStore()

        write_issues = store.write(importers.ExcelImporter(catalog.hello_world_pump))

        assert not write_issues.errors

        transform_issues = store.transform(transformer=transformers.VerifyDMSRules(errors="raise"))

        assert not transform_issues.errors

        read_issues = store.read(exporters.YAMLExporter())

        assert not read_issues.errors

        entity = store.get_last_entity()

        data_regression.check(yaml.safe_load(entity.result))
