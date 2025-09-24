import pytest
import yaml
from pytest_regressions.data_regression import DataRegressionFixture

from cognite.neat.v0.core._data_model import catalog, exporters, importers, transformers
from cognite.neat.v0.core._data_model.models import ConceptualDataModel, PhysicalDataModel
from cognite.neat.v0.core._data_model.transformers import VerifiedDataModelTransformer
from cognite.neat.v0.core._issues.errors import NeatValueError
from cognite.neat.v0.core._store import NeatDataModelStore
from cognite.neat.v0.core._store.exceptions import InvalidActivityInput


class FailingTransformer(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel]):
    def transform(self, rules: PhysicalDataModel) -> PhysicalDataModel:
        raise NeatValueError("This transformer always fails")

    @property
    def description(self) -> str:
        return "Failing transformer"


class FailingExporter(exporters.BaseExporter[PhysicalDataModel, str]):
    @property
    def description(self) -> str:
        return "Failing exporter"

    def export_to_file(self, data_model: PhysicalDataModel, filepath: str) -> None:
        raise NeatValueError("This exporter always fails")

    def export(self, data_model: PhysicalDataModel) -> str:
        raise NeatValueError("This exporter always fails")


class TestRuleStore:
    def test_import_export(self, data_regression: DataRegressionFixture) -> None:
        store = NeatDataModelStore()

        import_issues = store.import_data_model(importers.ExcelImporter(catalog.hello_world_pump), validate=False)

        assert not import_issues.errors

        result = store.export(exporters.YAMLExporter())

        assert isinstance(result, str)

        data_regression.check(yaml.safe_load(result))

    def test_import_fail_transform(self) -> None:
        store = NeatDataModelStore()

        import_issues = store.import_data_model(importers.ExcelImporter(catalog.hello_world_pump), validate=False)

        assert not import_issues.errors

        transform_issues = store.transform(FailingTransformer())

        assert len(transform_issues.errors) == 1
        error = transform_issues.errors[0]
        assert isinstance(error, NeatValueError)
        assert "This transformer always fails" in error.as_message()

    def test_import_invalid_transformer(self) -> None:
        store = NeatDataModelStore()

        import_issues = store.import_data_model(importers.ExcelImporter(catalog.hello_world_pump), validate=False)

        assert not import_issues.errors

        with pytest.raises(InvalidActivityInput) as exc_info:
            _ = store.transform(transformers.ToCompliantEntities())

        assert exc_info.value.expected == (ConceptualDataModel,)
        assert exc_info.value.have == (PhysicalDataModel,)

    def test_raise_exception_in_exporter(self) -> None:
        store = NeatDataModelStore()

        import_issues = store.import_data_model(importers.ExcelImporter(catalog.hello_world_pump), validate=False)

        assert not import_issues.errors

        store.export(FailingExporter())

        assert store.last_issues
        assert len(store.last_issues.errors) == 1
        error = store.last_issues.errors[0]
        assert isinstance(error, NeatValueError)
        assert "This exporter always fails" in error.as_message()
