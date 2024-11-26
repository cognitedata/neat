from cognite.neat._rules import importers
from cognite.neat._rules.transformers import ImporterPipeline
from tests.config import IMF_EXAMPLE


def test_imf_importer():
    rules = ImporterPipeline.verify(importers.IMFImporter.from_file(IMF_EXAMPLE))

    assert len(rules.classes) == 63
    assert len(rules.properties) == 62
