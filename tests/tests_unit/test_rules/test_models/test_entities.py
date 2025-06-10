import pytest
from cognite.client.data_classes.data_modeling import DataModelId

from cognite.neat.core._data_model._constants import ENTITY_PATTERN
from cognite.neat.core._data_model.models.entities import (
    AssetEntity,
    ConceptEntity,
    ConceptualEntity,
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
from cognite.neat.core._issues.errors import NeatValueError

DEFAULT_SPACE = "sp_my_space"
DEFAULT_VERSION = "vDefault"


TEST_CASES = [
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
