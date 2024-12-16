import yaml
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat._rules import catalog, exporters, importers, transformers
from cognite.neat._store import NeatRulesStore


class TestRuleStore:
    def test_write_transform_read(self, deterministic_uuid4: None, data_regression: DataRegressionFixture) -> None:
        store = NeatRulesStore()

        write_issues = store.write(importers.ExcelImporter(catalog.hello_world_pump))

        assert not write_issues.errors

        transform_issues = store.transform(transformer=transformers.VerifyDMSRules(errors="raise", validate=False))

        assert not transform_issues.errors

        result = store.read(exporters.YAMLExporter())

        assert isinstance(result, str)
        data_regression.check(yaml.safe_load(result))
