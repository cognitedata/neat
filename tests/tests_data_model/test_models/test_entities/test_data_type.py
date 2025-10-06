from cognite.neat._data_model._constants import XML_SCHEMA_NAMESPACE
from cognite.neat._data_model.models.entities._data_types import Enum, EnumCollectionEntity, Long, UnitEntity


def test_long() -> None:
    long_type = Long(unit=UnitEntity(prefix="qudt", suffix="meter"))
    assert long_type.suffix == "long"
    assert long_type.prefix == "xsd"
    assert long_type.python is int
    assert long_type.xsd == XML_SCHEMA_NAMESPACE["long"]
    assert str(long_type) == "xsd:long(unit=qudt:meter)"


def test_enum() -> None:
    collection = EnumCollectionEntity(prefix="cdf", suffix="assetTypes")
    enum_type = Enum(collection=collection, unknown_value="pump")
    assert enum_type.suffix == "enum"
    assert enum_type.prefix == "xsd"
    assert enum_type.xsd == XML_SCHEMA_NAMESPACE["enum"]
    assert str(enum_type) == "xsd:enum(collection=cdf:assetTypes,unknownValue=pump)"
