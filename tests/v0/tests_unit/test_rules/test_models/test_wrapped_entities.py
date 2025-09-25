from typing import Any

import pytest
from cognite.client import data_modeling as dm

from cognite.neat.v0.core._data_model import importers
from cognite.neat.v0.core._data_model.models.entities import (
    ContainerEntity,
    DMSFilter,
    DMSNodeEntity,
    HasDataFilter,
    NodeTypeFilter,
    RawFilter,
    ViewEntity,
    WrappedEntity,
)
from cognite.neat.v0.core._data_model.transformers import VerifyPhysicalDataModel
from tests.v0 import config

RAW_FILTER_EXAMPLE = """{"and": [
    {
      "in": {
        "property": ["yggdrasil_domain_model", "EntityTypeGroup", "entityType"],
        "values": ["CFIHOS_00000003"]
      }
    }
  ]}"""

RAW_FILTER_CELL_EXAMPLE = f"""rawFilter({RAW_FILTER_EXAMPLE})"""
RAW_FILTER_WITH_AMPERSAND = (
    '{"equals": {"property": ["ne-013-i4-neat-g-m-spc", "Tag/1", "TagCategoryDescription"], '
    '"value": "FIRE & GAS FIELD EQUIPMENT"}}'
)


class TestWrappedEntities:
    @pytest.mark.parametrize(
        "cls_, raw, expected",
        [
            (
                NodeTypeFilter,
                "NodeType(subject:person)",
                NodeTypeFilter(inner=[DMSNodeEntity(space="subject", externalId="person")]),
            ),
            (
                HasDataFilter,
                "HasData(subject:person)",
                HasDataFilter(inner=[ContainerEntity(space="subject", externalId="person")]),
            ),
            (NodeTypeFilter, "nodeType", NodeTypeFilter()),
            (HasDataFilter, "hasData", HasDataFilter()),
            (
                HasDataFilter,
                "hasData(space:container1, space:container2)",
                HasDataFilter(
                    inner=[
                        ContainerEntity(space="space", externalId="container1"),
                        ContainerEntity(space="space", externalId="container2"),
                    ]
                ),
            ),
            (
                NodeTypeFilter,
                "nodeType(space:node1, space:node2)",
                NodeTypeFilter(
                    inner=[
                        DMSNodeEntity(space="space", externalId="node1"),
                        DMSNodeEntity(space="space", externalId="node2"),
                    ]
                ),
            ),
            (
                RawFilter,
                RAW_FILTER_CELL_EXAMPLE,
                RawFilter(filter=RAW_FILTER_EXAMPLE),
            ),
            (
                RawFilter,
                f"rawFilter({RAW_FILTER_WITH_AMPERSAND})",
                RawFilter(filter=RAW_FILTER_WITH_AMPERSAND),
            ),
        ],
    )
    def test_load(self, cls_: type[WrappedEntity], raw: Any, expected: WrappedEntity) -> None:
        loaded = cls_.load(raw)

        assert loaded == expected
        assert repr(loaded) == repr(expected)
        assert str(loaded) == str(expected)

    @pytest.mark.parametrize(
        "filter_, expected",
        [
            (
                dm.filters.HasData(containers=[dm.ContainerId(space="space", external_id="container1")]),
                HasDataFilter(inner=[ContainerEntity(space="space", externalId="container1")]),
            ),
            (
                dm.filters.HasData(views=[dm.ViewId(space="space", external_id="view1", version="v1")]),
                HasDataFilter(inner=[ViewEntity(space="space", externalId="view1", version="v1")]),
            ),
            (
                dm.filters.Equals(["node", "type"], {"space": "space", "externalId": "node1"}),
                NodeTypeFilter(inner=[DMSNodeEntity(space="space", externalId="node1")]),
            ),
            (
                dm.filters.In(
                    ["node", "type"],
                    [
                        {"space": "space", "externalId": "node1"},
                        {"space": "space", "externalId": "node2"},
                    ],
                ),
                NodeTypeFilter(
                    inner=[
                        DMSNodeEntity(space="space", externalId="node1"),
                        DMSNodeEntity(space="space", externalId="node2"),
                    ]
                ),
            ),
            (
                dm.filters.In(
                    property=["cdf_cdm", "CogniteFile", "mimeType"],
                    values=[
                        "application/pdf",
                        "application/msword",
                        "image/jpeg",
                        "image/tiff",
                        "image/png",
                        "application/vnd.ms-excel",
                        "application/vnd.ms-excel.sheet.macroEnabled.12",
                    ],
                ),
                RawFilter(
                    filter=(
                        'rawFilter({"in": {"property": ["cdf_cdm", "CogniteFile", "mimeType"], '
                        '"values": ["application/pdf", "application/msword", "image/jpeg", '
                        '"image/tiff", "image/png", "application/vnd.ms-excel", '
                        '"application/vnd.ms-excel.sheet.macroEnabled.12"]}})'
                    )
                ),
            ),
            pytest.param(
                dm.filters.Equals(["govern-space", "Property", "type"], "Input"),
                RawFilter(filter='{"equals": {"property": ["govern-space", "Property", "type"], "value": "Input"}}'),
                id="Equal filter on property",
            ),
        ],
    )
    def test_from_dms_filter(self, filter_: dm.Filter, expected: DMSFilter) -> None:
        loaded = DMSFilter.from_dms_filter(filter_)

        assert loaded == expected

    def test_has_data_vs_raw_filter(self) -> None:
        assert (
            HasDataFilter.load("hasData(space:container1)").as_dms_filter().dump()
            == RawFilter.load(
                """rawFilter({"hasData": [{"type": "container",
                                           "space": "space",
                                           "externalId": "container1"}]})"""
            )
            .as_dms_filter()
            .dump()
        )

    def test_raw_filter_in_sheet(self) -> None:
        read_rules = importers.ExcelImporter(
            config.DOC_RULES / "dms-architect-rules-raw-filter-example.xlsx"
        ).to_data_model()
        rules = VerifyPhysicalDataModel().transform(read_rules)

        assert rules.views[0].filter_ == RawFilter.load(
            """rawFilter({"equals": {"property": ["node", "type"],
                "value": {"space": "power", "externalId": "WindTurbine"}}})"""
        )
