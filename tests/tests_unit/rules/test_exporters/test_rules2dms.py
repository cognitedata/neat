import re
import zipfile
from collections import Counter
from pathlib import Path

from cognite.neat.rules.exporters._rules2dms import DMSExporter
from cognite.neat.rules.models._rules.dms_architect_rules import (
    DMSRules,
)


class TestDMSExporter:
    def test_export_dms_schema_to_zip(self, alice_rules: DMSRules, tmp_path: Path) -> None:
        exporter = DMSExporter()
        schema = exporter.export(alice_rules)
        zipfile_path = tmp_path / "test.zip"

        exporter.export_to_file(zipfile_path)

        counts = Counter()
        with zipfile.ZipFile(zipfile_path, "r") as zip_ref:
            for name in zip_ref.namelist():
                matches = re.search(r"[a-zA-Z0-9_].(space|datamodel|view|container).yaml$", name)
                counts.update([matches.group(1)])

        assert counts["space"] == len(schema.spaces)
        assert counts["datamodel"] == len(schema.data_models)
        assert counts["view"] == len(schema.views)
        assert counts["container"] == len(schema.containers)
