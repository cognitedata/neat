import pytest
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
    def test_import_transform_export(self, data_regression: DataRegressionFixture) -> None:
        store = NeatRulesStore()

        import_issues = store.import_(importers.ExcelImporter(catalog.hello_world_pump))

        assert not import_issues.errors

        transform_issues = store.transform(transformers.VerifyDMSRules(validate=False))

        assert not transform_issues.errors

        result = store.export(exporters.YAMLExporter())

        assert isinstance(result, str)
        last_entity = store.get_last_successful_entity()
        assert last_entity.result == result

        data_regression.check(yaml.safe_load(result))

    def test_import_fail_transform(self) -> None:
        store = NeatRulesStore()

        import_issues = store.import_(importers.ExcelImporter(catalog.hello_world_pump))

        assert not import_issues.errors

        transform_issues = store.transform(FailingTransformer())

        assert len(transform_issues.errors) == 1
        error = transform_issues.errors[0]
        assert isinstance(error, NeatValueError)
        assert "This transformer always fails" in error.as_message()

    def test_import_invalid_transformer(self) -> None:
        store = NeatRulesStore()

        import_issues = store.import_(importers.ExcelImporter(catalog.hello_world_pump))

        assert not import_issues.errors

        with pytest.raises(NeatValueError):
            _ = store.transform(transformers.VerifyInformationRules(validate=False))

    def test_import_prune_until_compatible(self) -> None:
        store = NeatRulesStore()
        # Gives us unverified information rules
        issues = store.import_(importers.ExcelImporter(catalog.imf_attributes))

        assert not issues
        # Verify the information rules
        issues = store.transform(transformers.VerifyInformationRules(validate=False))
        assert not issues

        # We want ot run a transformer on unverified rules, so we need to go back to the unverified state
        next_transformer = transformers.ToCompliantEntities()
        pruned = store.prune_until_compatible(next_transformer)
        # Removes the VerifiedInformationRules
        assert len(pruned) == 1

        issues = store.transform(next_transformer)
        assert not issues
