from abc import ABC

import pytest

from cognite.neat.v0.core._data_model.exporters import BaseExporter, CDFExporter
from cognite.neat.v0.core._data_model.models import ConceptualDataModel, PhysicalDataModel

EXPORTER_CLS = [subclass for subclass in BaseExporter.__subclasses__() if subclass is not CDFExporter] + list(
    CDFExporter.__subclasses__()
)


def instansiated_exporters_cls() -> list[BaseExporter]:
    for exporter_cls in EXPORTER_CLS:
        if ABC in exporter_cls.__bases__:
            continue
        yield exporter_cls()


class TestExporters:
    @pytest.mark.parametrize(
        "exporter_cls",
        EXPORTER_CLS,
    )
    def test_valid_source_type(self, exporter_cls: type[BaseExporter]) -> None:
        valid_sources = {PhysicalDataModel, ConceptualDataModel}

        source_types = exporter_cls.source_types()

        invalid_sources = set(source_types) - valid_sources

        assert not invalid_sources, f"Invalid source types: {invalid_sources}"

    @pytest.mark.parametrize("exporter", [pytest.param(v, id=type(v).__name__) for v in instansiated_exporters_cls()])
    def test_has_description(self, exporter: BaseExporter) -> None:
        assert exporter.description != "MISSING DESCRIPTION", f"Missing description for {exporter}"
