from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from cognite.neat._rules.exporters import ExcelExporter
from cognite.neat._rules.exporters._rules2excel import _MetadataCreator
from cognite.neat._rules.models import (
    DataModelType,
    DMSRules,
    DomainRules,
    ExtensionCategory,
    InformationRules,
    RoleTypes,
    SchemaCompleteness,
)
from cognite.neat._rules.models.dms import DMSMetadata
from cognite.neat._rules.models.domain import DomainMetadata
from cognite.neat._rules.models.information import InformationMetadata


class TestExcelExporter:
    def test_export_dms_rules(self, alice_rules: DMSRules):
        exporter = ExcelExporter(styling="maximal")
        workbook = exporter.export(alice_rules)
        assert "Metadata" in workbook.sheetnames
        assert "Containers" in workbook.sheetnames
        assert "Views" in workbook.sheetnames
        assert "Properties" in workbook.sheetnames

    def test_export_information_rules(self, david_rules: InformationRules):
        exporter = ExcelExporter()
        workbook = exporter.export(david_rules)

        assert "Metadata" in workbook.sheetnames
        assert "Classes" in workbook.sheetnames
        assert "Properties" in workbook.sheetnames

    def test_export_domain_rules(self, jon_rules: DomainRules):
        exporter = ExcelExporter()
        workbook = exporter.export(jon_rules)

        assert "Metadata" in workbook.sheetnames
        assert "Properties" in workbook.sheetnames

    def test_export_domain_rules_emma(self, emma_rules: DomainRules):
        exporter = ExcelExporter()
        workbook = exporter.export(emma_rules)

        assert "Metadata" in workbook.sheetnames
        assert "Properties" in workbook.sheetnames
        assert "Classes" in workbook.sheetnames

    def test_export_dms_rules_alice_reference(self, alice_rules: DMSRules) -> None:
        exporter = ExcelExporter(styling="maximal", dump_as="reference")
        workbook = exporter.export(alice_rules)

        assert "Metadata" in workbook.sheetnames
        assert "Containers" in workbook.sheetnames
        assert "Views" in workbook.sheetnames
        assert "Properties" in workbook.sheetnames

        assert "RefProperties" in workbook.sheetnames
        assert "RefContainers" in workbook.sheetnames
        assert "RefViews" in workbook.sheetnames

        rows = next((rows for rows in workbook["RefProperties"].columns if rows[1].value == "Reference"), None)
        assert rows is not None, "Reference column not found in RefProperties sheet"

        # Two first rows are headers
        reference_count = sum(1 for row in rows[2:] if row.value is not None)
        assert reference_count >= len(alice_rules.properties)

        rows = next((rows for rows in workbook["RefContainers"].columns if rows[1].value == "Reference"), None)
        assert rows is not None, "Reference column not found in RefContainers sheet"
        assert sum(1 for row in rows[2:] if row.value is not None) >= len(alice_rules.containers)

        rows = next((rows for rows in workbook["RefViews"].columns if rows[1].value == "Reference"), None)
        assert rows is not None, "Reference column not found in RefViews sheet"
        assert sum(1 for row in rows[2:] if row.value is not None) >= len(alice_rules.views)

    @pytest.mark.parametrize(
        "dump_as, expected_sheet_names",
        [
            (
                "user",
                {
                    "Metadata",
                    "Classes",
                    "Properties",
                    "Prefixes",
                    "RefMetadata",
                    "RefClasses",
                    "RefProperties",
                },
            ),
            (
                "last",
                {
                    "Metadata",
                    "Classes",
                    "Properties",
                    "Prefixes",
                    "LastClasses",
                    "LastProperties",
                    "LastMetadata",
                    "RefMetadata",
                    "RefClasses",
                    "RefProperties",
                },
            ),
        ],
    )
    def test_export_olav_rules_dump_as(
        self, dump_as: ExcelExporter.DumpOptions, expected_sheet_names: set[str], olav_rules: InformationRules
    ) -> None:
        exporter = ExcelExporter(styling="maximal", dump_as=dump_as)
        assert olav_rules.reference is not None, "Olav rules are expected to have a reference set"
        # Make a copy of the rules to avoid changing the original
        olav_copy = olav_rules.model_copy(deep=True)

        workbook = exporter.export(olav_copy)

        missing = expected_sheet_names - set(workbook.sheetnames)
        assert not missing, f"Missing sheets: {missing}"
        extra = set(workbook.sheetnames) - expected_sheet_names
        assert not extra, f"Extra sheets: {extra}"


def metadata_creator_test_cases():
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    past_long_ago = now.replace(year=now.year - 10)
    recent_past = now.replace(year=now.year - 1)
    creator = _MetadataCreator("create")
    yield pytest.param(
        creator,
        DomainMetadata(creator="Alice"),
        now,
        {"role": RoleTypes.domain_expert.value, "creator": "<YOUR NAME>"},
        id="Domain metadata, create without reference",
    )

    creator = _MetadataCreator("create", ("sp_solution", "new_solution"))

    yield pytest.param(
        creator,
        DMSMetadata(
            data_model_type=DataModelType.enterprise,
            schema_=SchemaCompleteness.complete,
            space="sp_enterprise",
            external_id="enterprise",
            version="1",
            creator=["Bob"],
            created=past_long_ago,
            updated=recent_past,
        ),
        now,
        {
            "role": RoleTypes.dms.value,
            "dataModelType": DataModelType.solution.value,
            "schema": SchemaCompleteness.complete.value,
            "space": "sp_solution",
            "externalId": "new_solution",
            "version": "1",
            "name": "new_solution",
            "description": None,
            "creator": "<YOUR NAME>",
            "created": now.isoformat(),
            "updated": now.isoformat(),
        },
        id="Create solution model",
    )
    creator = _MetadataCreator("update", None)

    yield pytest.param(
        creator,
        DMSMetadata(
            data_model_type=DataModelType.solution,
            schema_=SchemaCompleteness.extended,
            space="sp_solution",
            external_id="my_solution",
            version="1",
            creator=["Bob"],
            created=past_long_ago,
            updated=recent_past,
        ),
        now,
        {
            "role": RoleTypes.dms.value,
            "dataModelType": DataModelType.solution.value,
            "schema": SchemaCompleteness.extended.value,
            "extension": ExtensionCategory.addition.value,
            "space": "sp_solution",
            "externalId": "my_solution",
            "version": "1",
            "name": None,
            "description": None,
            "creator": "Bob, <YOUR NAME>",
            "created": past_long_ago.isoformat(),
            "updated": now.isoformat(),
        },
        id="Update solution model",
    )

    creator = _MetadataCreator("update", None)

    yield pytest.param(
        creator,
        DMSMetadata(
            data_model_type=DataModelType.enterprise,
            schema_=SchemaCompleteness.complete,
            space="sp_enterprise",
            external_id="enterprise",
            version="1",
            creator=["Bob"],
            created=past_long_ago,
            updated=recent_past,
        ),
        now,
        {
            "role": RoleTypes.dms.value,
            "dataModelType": DataModelType.enterprise.value,
            "schema": SchemaCompleteness.extended.value,
            "extension": ExtensionCategory.addition.value,
            "space": "sp_enterprise",
            "externalId": "enterprise",
            "version": "1",
            "name": None,
            "description": None,
            "creator": "Bob, <YOUR NAME>",
            "created": past_long_ago.isoformat(),
            "updated": now.isoformat(),
        },
        id="Update enterprise model",
    )


class TestMetadataCreator:
    @pytest.mark.parametrize("creator, metadata, now, expected", list(metadata_creator_test_cases()))
    def test_create(
        self,
        creator: _MetadataCreator,
        now: datetime,
        metadata: DomainMetadata | InformationMetadata | DMSMetadata,
        expected: dict[str, str],
    ):
        with freeze_time(now):
            actual = creator.create(metadata)

        assert actual == expected
