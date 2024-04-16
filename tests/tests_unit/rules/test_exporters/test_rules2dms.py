import re
import zipfile
from collections import Counter
from pathlib import Path
from typing import cast

from cognite.neat.rules.exporters._rules2dms import DMSExporter
from cognite.neat.rules.models._rules.dms_architect_rules import (
    DMSRules,
)
from cognite.neat.rules.models._rules.dms_schema import PipelineSchema


class TestDMSExporter:
    def test_export_dms_schema_to_zip(self, alice_rules: DMSRules, tmp_path: Path) -> None:
        exporter = DMSExporter()
        schema = exporter.export(alice_rules)
        zipfile_path = tmp_path / "test.zip"

        exporter.export_to_file(alice_rules, zipfile_path)

        counts = Counter()
        with zipfile.ZipFile(zipfile_path, "r") as zip_ref:
            for name in zip_ref.namelist():
                matches = re.search(r"[a-zA-Z0-9_].(space|datamodel|view|container|node).yaml$", name)
                counts.update([matches.group(1)])

        assert counts["space"] == len(schema.spaces)
        assert counts["datamodel"] == len(schema.data_models)
        assert counts["view"] == len(alice_rules.views)
        assert counts["container"] == len(alice_rules.containers)
        assert counts["node"] == len(schema.node_types)

    def test_export_dms_schema_with_pipeline(self, alice_rules: DMSRules, tmp_path) -> None:
        exporter = DMSExporter(export_pipeline=True)
        schema = cast(PipelineSchema, exporter.export(alice_rules))
        exporter.export_to_file(alice_rules, tmp_path)

        counts = Counter()
        for yaml_file in (tmp_path / "data_models").rglob("*.yaml"):
            if "." in yaml_file.stem:
                resource_type = yaml_file.stem.rsplit(".")[-1]
                counts.update([resource_type])
        transformation_count = len(list((tmp_path / "transformations").rglob("*.yaml")))
        table_count = len(list((tmp_path / "raw").rglob("*.yaml")))

        assert counts["space"] == len(schema.spaces)
        assert counts["datamodel"] == len(schema.data_models)
        assert counts["view"] == len(schema.views)
        assert counts["container"] == len(schema.containers)
        assert transformation_count == len(schema.transformations)
        assert table_count == len(schema.raw_tables)
