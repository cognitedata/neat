import pytest
import yaml
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat.core._issues.errors import NeatValueError
from cognite.neat.core._rules import catalog, exporters, importers, transformers
from cognite.neat.core._rules.models import DMSRules, InformationRules
from cognite.neat.core._rules.transformers import VerifiedRulesTransformer
from cognite.neat.core._store import NeatRulesStore
from cognite.neat.core._store.exceptions import InvalidActivityInput


class FailingTransformer(VerifiedRulesTransformer[DMSRules, DMSRules]):
    def transform(self, rules: DMSRules) -> DMSRules:
        raise NeatValueError("This transformer always fails")

    @property
    def description(self) -> str:
        return "Failing transformer"


class TestRuleStore:
    def test_import_export(self, data_regression: DataRegressionFixture) -> None:
        store = NeatRulesStore()

        import_issues = store.import_rules(importers.ExcelImporter(catalog.hello_world_pump), validate=False)

        assert not import_issues.errors

        result = store.export(exporters.YAMLExporter())

        assert isinstance(result, str)

        data_regression.check(yaml.safe_load(result))

    def test_import_fail_transform(self) -> None:
        store = NeatRulesStore()

        import_issues = store.import_rules(importers.ExcelImporter(catalog.hello_world_pump), validate=False)

        assert not import_issues.errors

        transform_issues = store.transform(FailingTransformer())

        assert len(transform_issues.errors) == 1
        error = transform_issues.errors[0]
        assert isinstance(error, NeatValueError)
        assert "This transformer always fails" in error.as_message()

    def test_import_invalid_transformer(self) -> None:
        store = NeatRulesStore()

        import_issues = store.import_rules(importers.ExcelImporter(catalog.hello_world_pump), validate=False)

        assert not import_issues.errors

        with pytest.raises(InvalidActivityInput) as exc_info:
            _ = store.transform(transformers.ToCompliantEntities())

        assert exc_info.value.expected == (InformationRules,)
        assert exc_info.value.have == (DMSRules,)
