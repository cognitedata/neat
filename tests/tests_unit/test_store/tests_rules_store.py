import yaml
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat._issues.errors import NeatValueError
from cognite.neat._rules import catalog, exporters, importers, transformers
from cognite.neat._rules.models import DMSInputRules, DMSRules
from cognite.neat._rules.transformers import RulesTransformer
from cognite.neat._store import NeatRulesStore


class FailingTransformer(RulesTransformer[DMSInputRules, DMSRules]):
    def transform(self, rules: DMSInputRules) -> DMSRules:
        raise NeatValueError("This transformer always fails")


class TestRuleStore:
    def test_write_transform_read(self, deterministic_uuid4: None, data_regression: DataRegressionFixture) -> None:
        store = NeatRulesStore()

        write_issues = store.import_(importers.ExcelImporter(catalog.hello_world_pump))

        assert not write_issues.errors

        transform_issues = store.transform(transformers.VerifyDMSRules(validate=False))

        assert not transform_issues.errors

        result = store.export(exporters.YAMLExporter())

        assert isinstance(result, str)
        last_entity = store.get_last_successful_entity()
        assert last_entity.result == result

        data_regression.check(yaml.safe_load(result))

    def test_write_fail_transform(self, deterministic_uuid4: None) -> None:
        store = NeatRulesStore()

        write_issues = store.import_(importers.ExcelImporter(catalog.hello_world_pump))

        assert not write_issues.errors

        transform_issues = store.transform(FailingTransformer())

        assert len(transform_issues.errors) == 1
        error = transform_issues.errors[0]
        assert isinstance(error, NeatValueError)
        assert "This transformer always fails" in error.as_message()
