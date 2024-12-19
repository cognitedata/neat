import pytest

from cognite.neat._rules.exporters import BaseExporter, CDFExporter
from cognite.neat._rules.models import DMSRules, InformationRules


class TestExporters:
    @pytest.mark.parametrize(
        "exporter_cls",
        [subclass for subclass in BaseExporter.__subclasses__() if subclass is not CDFExporter]
        + list(CDFExporter.__subclasses__()),
    )
    def test_valid_source_type(self, exporter_cls: type[BaseExporter]) -> None:
        valid_sources = {DMSRules, InformationRules}

        source_types = exporter_cls.source_type()

        invalid_sources = set(source_types) - valid_sources

        assert not invalid_sources, f"Invalid source types: {invalid_sources}"
