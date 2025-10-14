from urllib.parse import quote

import pytest
from cognite.client.data_classes.data_modeling import DataModelId

from cognite.neat.v0.core._data_model._constants import ENTITY_PATTERN, PATTERNS
from cognite.neat.v0.core._data_model.models.entities import (
    AssetEntity,
    ConceptEntity,
    ConceptualEntity,
    ContainerConstraintEntity,
    ContainerIndexEntity,
    DataModelEntity,
    DMSNodeEntity,
    EdgeEntity,
    PhysicalEntity,
    PhysicalUnknownEntity,
    ReferenceEntity,
    RelationshipEntity,
    UnitEntity,
    UnknownEntity,
    ViewEntity,
)
from cognite.neat.v0.core._data_model.models.entities._single_value import ContainerEntity
from cognite.neat.v0.core._issues.errors import NeatValueError

DEFAULT_SPACE = "sp_my_space"
DEFAULT_VERSION = "vDefault"


TEST_CASES = [
    (
        ContainerConstraintEntity,
        "uniqueness:name",
        ContainerConstraintEntity(prefix="uniqueness", suffix="name"),
    ),
    (
        ContainerConstraintEntity,
        "requires:my_space_Asset(require=my_space:Asset)",
        ContainerConstraintEntity(
            prefix="requires", suffix="my_space_Asset", require=ContainerEntity(space="my_space", externalId="Asset")
        ),
    ),
    (
        ContainerIndexEntity,
        "name",
        ContainerIndexEntity(suffix="name"),
    ),
    (
        ContainerIndexEntity,
        "name(cursorable=True)",
        ContainerIndexEntity(suffix="name", cursorable=True),
    ),
    (
        ContainerIndexEntity,
        "name(cursorable=True)",
        ContainerIndexEntity(suffix="name", cursorable=True),
    ),
    (
        ContainerIndexEntity,
        "name(bySpace=True,cursorable=True)",
        ContainerIndexEntity(suffix="name", cursorable=True, bySpace=True),
    ),
    (
        ContainerIndexEntity,
        "btree:name(bySpace=True,cursorable=True)",
        ContainerIndexEntity(prefix="btree", suffix="name", cursorable=True, bySpace=True),
    ),
    (
        ContainerIndexEntity,
        "inverted:tags",
        ContainerIndexEntity(prefix="inverted", suffix="tags"),
    ),
    (
        UnitEntity,
        "acceleration:ft-per-sec2",
        UnitEntity(prefix="acceleration", suffix="ft-per-sec2"),
    ),
    (
        UnitEntity,
        "length:m",
        UnitEntity(prefix="length", suffix="m"),
    ),
    (
        ConceptEntity,
        "person",
        ConceptEntity(prefix=DEFAULT_SPACE, suffix="person", version=DEFAULT_VERSION),
    ),
    (
        ConceptEntity,
        "cdf_cdm:CogniteAsset(version=v1)",
        ConceptEntity(prefix="cdf_cdm", suffix="CogniteAsset", version="v1"),
    ),
    (
        ConceptEntity,
        "cdf_cdm:Concept(version=v1)",
        ConceptEntity(prefix="cdf_cdm", suffix="Concept", version="v1"),
    ),
    (
        ConceptEntity,
        "cdf_cdm:Conceptual%20%Concept(version=v1)",
        ConceptEntity(prefix="cdf_cdm", suffix="Conceptual%20%Concept", version="v1"),
    ),
    (
        ViewEntity,
        "subject:person(version=1.0)",
        ViewEntity(space="subject", externalId="person", version="1.0"),
    ),
    (UnknownEntity, "#N/A", UnknownEntity()),
    (
        ViewEntity,
        "Person",
        ViewEntity(space=DEFAULT_SPACE, externalId="Person", version=DEFAULT_VERSION),
    ),
    (
        ViewEntity,
        "#N/A",
        PhysicalUnknownEntity.from_id(None),
    ),
    (
        ConceptEntity,
        "#N/A",
        UnknownEntity(),
    ),
    (
        AssetEntity,
        "Asset(property=externalId)",
        AssetEntity(property="externalId"),
    ),
    (
        RelationshipEntity,
        "Relationship(label=cool-label)",
        RelationshipEntity(label="cool-label"),
    ),
    (
        EdgeEntity,
        "edge(properties=Owns,type=ownership)",
        EdgeEntity(
            properties=ViewEntity(space=DEFAULT_SPACE, version=DEFAULT_VERSION, externalId="Owns"),
            type=DMSNodeEntity(space=DEFAULT_SPACE, externalId="ownership"),
        ),
    ),
    (
        EdgeEntity,
        "edge(properties=my_other_space:Owns(version=34),type=ownership)",
        EdgeEntity(
            properties=ViewEntity(space="my_other_space", version="34", externalId="Owns"),
            type=DMSNodeEntity(space=DEFAULT_SPACE, externalId="ownership"),
        ),
    ),
    (
        EdgeEntity,
        "edge(type=my_node_type_space:ownership)",
        EdgeEntity(
            type=DMSNodeEntity(space="my_node_type_space", externalId="ownership"),
        ),
    ),
    (
        EdgeEntity,
        "edge(type=MySpace:ns=3;i=4924)",
        EdgeEntity(
            type=DMSNodeEntity(space="MySpace", externalId="ns=3;i=4924"),
        ),
    ),
    (
        EdgeEntity,
        "edge(direction=inwards,properties=StartEndTime)",
        EdgeEntity(
            properties=ViewEntity(space=DEFAULT_SPACE, version=DEFAULT_VERSION, externalId="StartEndTime"),
            direction="inwards",
        ),
    ),
]


class TestEntities:
    @pytest.mark.parametrize(
        "cls_, raw, expected", TEST_CASES, ids=[f"{cls_.__name__} {raw}" for cls_, raw, _ in TEST_CASES]
    )
    def test_load_dump(self, cls_: type[ConceptualEntity], raw: str, expected: ConceptualEntity) -> None:
        if issubclass(cls_, PhysicalEntity):
            defaults = {"space": DEFAULT_SPACE, "version": DEFAULT_VERSION}
        elif issubclass(cls_, AssetEntity | RelationshipEntity | ContainerIndexEntity):
            defaults = {}
        else:
            defaults = {"prefix": DEFAULT_SPACE, "version": DEFAULT_VERSION}

        loaded = cls_.load(raw, **defaults)

        assert loaded == expected

        dumped = loaded.dump(**defaults)
        assert dumped == raw

    def test_load_bad_entity(self) -> None:
        with pytest.raises(ValueError) as e:
            ViewEntity.load("bad(entity)", space=DEFAULT_SPACE, version=DEFAULT_VERSION)
        error = e.value.errors()[0]["ctx"]["error"]
        assert NeatValueError("Invalid view entity: 'bad(entity)'") == error

    @pytest.mark.parametrize(
        "entity1, entity2",
        [
            (
                ContainerIndexEntity(prefix="btree", suffix="name", cursorable=True),
                ContainerIndexEntity(prefix="btree", suffix="name", cursorable=False),
            ),
        ],
    )
    def test_are_not_equal(self, entity1: ConceptualEntity, entity2: ConceptualEntity) -> None:
        assert entity1 != entity2, f"Expected {entity1} and {entity2} to be different entities"

    @pytest.mark.parametrize(
        "propety_id",
        [
            "耐久性",
            "信頼性",
            "効率",
            "精度",
            "柔軟性",
            "スケーラビリティ",
            "持続可能性",
            "保守性",
            "安全性",
            "オートメーション",
            "標準化",
            "統合",
            "モジュール性",
            "費用対効果",
            "生産性",
            "革新",
            "品質",
            "負荷容量",
            "耐熱性",
            "耐食性",
            "エネルギー効率",
            "環境への親しみやすさ",
            "ノイズリダクション",
            "サイクル時間",
            "スループット",
        ],
    )
    def test_conceptual_property(self, propety_id: str) -> None:
        encoded_prop = quote(propety_id, safe="")
        assert PATTERNS.conceptual_property_id_compliance.match(encoded_prop), (
            f"Property ID '{propety_id}' should be valid but is not."
        )

    @pytest.mark.parametrize(
        "cls_, raw",
        [
            pytest.param(ContainerIndexEntity, "notAnIndexType:name(bySpace=True,cursorable=True)", id="Bad prefix"),
            pytest.param(ViewEntity, "invalid(entity)format", id="ViewEntity - Invalid format"),
            pytest.param(ViewEntity, "bad:entity(invalid=parameter)", id="ViewEntity - Invalid parameter"),
            pytest.param(
                ConceptEntity,
                "malformed:entity(invalid(nested)parens)",
                id="ConceptEntity - Invalid nested parentheses",
            ),
            pytest.param(
                EdgeEntity,
                "edge(type=invalid:type,properties=malformed)",
                id="EdgeEntity - Invalid type and properties",
            ),
            pytest.param(DataModelEntity, "data_model(invalid_param=value)", id="DataModelEntity - Invalid parameter"),
            pytest.param(UnitEntity, ":missing_prefix", id="UnitEntity - Missing prefix"),
            pytest.param(AssetEntity, "Asset(invalid_property=value)", id="AssetEntity - Invalid property"),
            pytest.param(
                ReferenceEntity, "malformed_reference_without_proper_format", id="ReferenceEntity - Malformed format"
            ),
            pytest.param(
                ContainerIndexEntity, "invalid:index(invalidParam=true)", id="ContainerIndexEntity - Invalid parameter"
            ),
            pytest.param(
                ContainerIndexEntity,
                "btree:index(cursorable=invalid_bool)",
                id="ContainerIndexEntity - Invalid boolean value",
            ),
        ],
    )
    def test_load_return_on_failure(self, cls_: type[ConceptualEntity], raw: str) -> None:
        actual = cls_.load(raw, return_on_failure=True)
        assert actual == raw

    def test_direction_case_insensitive(self) -> None:
        defaults = {"space": DEFAULT_SPACE, "version": DEFAULT_VERSION}
        e1 = EdgeEntity.load("edge(direction=INWardS,properties=StartEndTime)", **defaults)
        e2 = EdgeEntity.load("edge(direction=OutWArds,properties=StartEndTime)", **defaults)

        assert e1.direction == "inwards"
        assert e2.direction == "outwards"


class TestEntityPattern:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("test:TestGraphQL1(version=3)", {"prefix": "test", "suffix": "TestGraphQL1", "content": "version=3"}),
            ("MyValue", {"prefix": "", "suffix": "MyValue", "content": None}),
            ("test:TestGraphQL1", {"prefix": "test", "suffix": "TestGraphQL1", "content": None}),
            (
                "test:TestGraphQL1(property=prop1)",
                {"prefix": "test", "suffix": "TestGraphQL1", "content": "property=prop1"},
            ),
            (
                "test:TestGraphQL1(property=test:prop1)",
                {"prefix": "test", "suffix": "TestGraphQL1", "content": "property=test:prop1"},
            ),
            (
                "MyValue(properties=prefix:suffix(version=v3), version=3)",
                {"prefix": "", "suffix": "MyValue", "content": "properties=prefix:suffix(version=v3), version=3"},
            ),
        ],
    )
    def test_match(self, raw: str, expected: dict[str, str]) -> None:
        assert ENTITY_PATTERN.match(raw).groupdict() == expected


class TestDataModelEntity:
    @pytest.mark.parametrize(
        "raw, expected, expected_id",
        [
            (
                "test:TestGraphQL1(version=3)",
                DataModelEntity(space="test", externalId="TestGraphQL1", version="3"),
                DataModelId("test", "TestGraphQL1", "3"),
            ),
            (
                "test:TestGraphQL1",
                DataModelEntity(space="test", externalId="TestGraphQL1", version=DEFAULT_VERSION),
                DataModelId("test", "TestGraphQL1", DEFAULT_VERSION),
            ),
        ],
    )
    def test_load(self, raw: str, expected: DataModelEntity, expected_id: DataModelId) -> None:
        actual = DataModelEntity.load(raw, space=DEFAULT_SPACE, version=DEFAULT_VERSION)

        assert actual == expected
        assert actual.as_id() == expected_id


class TestReferenceType:
    @pytest.mark.parametrize(
        "raw, expected,",
        [
            pytest.param(
                "test:TestGraphQL1(version=3, property=prop1)",
                ReferenceEntity(prefix="test", suffix="TestGraphQL1", version="3", property="prop1"),
                id="Prefix, suffix, version and prop",
            ),
            pytest.param(
                "test:TestGraphQL1(property=prop1)",
                ReferenceEntity(prefix="test", suffix="TestGraphQL1", version=None, property="prop1"),
                id="Prefix, suffix and prop. Skip version",
            ),
            pytest.param(
                "test:TestGraphQL1(property=test:prop1)",
                ReferenceEntity(
                    prefix="test",
                    suffix="TestGraphQL1",
                    version=None,
                    property="test:prop1",
                ),
                id="Prefix, suffix and prop. Skip version",
            ),
            pytest.param(
                "test:TestGraphQL1",
                ReferenceEntity(prefix="test", suffix="TestGraphQL1", version=None, property=None),
                id="Prefix, suffix and prop. Skip version",
            ),
        ],
    )
    def test_load(self, raw: str, expected: ReferenceEntity) -> None:
        actual = ReferenceEntity.load(raw)
        assert actual == expected
