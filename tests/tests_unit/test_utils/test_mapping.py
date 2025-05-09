import urllib.parse

from rdflib import Namespace

from cognite.neat.core._data_model.models.information import InformationInputClass, InformationInputProperty
from cognite.neat.core._utils.mapping import create_predicate_mapping, create_type_mapping


class TestCreateTypeMapping:
    def test_create_predicate_mapping(self) -> None:
        namespace = Namespace("http://example.org/")
        classes = [InformationInputClass("MyType", name="my$$$Type").as_verified(default_prefix="my_space")]
        mapping = create_type_mapping(classes, namespace)
        assert mapping == {namespace[urllib.parse.quote("my$$$Type")]: namespace["MyType"]}

    def test_create_predicate_mapping_no_namespace(self) -> None:
        classes = [InformationInputClass("MyType", name="my$$$Type").as_verified(default_prefix="my_space")]
        mapping = create_type_mapping(classes)
        assert mapping == {urllib.parse.quote("my$$$Type"): "MyType"}


class TestCreatePredicateMapping:
    def test_create_predicate_mapping(self) -> None:
        namespace = Namespace("http://example.org/")
        properties = [
            InformationInputProperty("myClass", "myProperty", "text", name="my###Property").as_verified(
                default_prefix="my_space"
            )
        ]

        mapping = create_predicate_mapping(properties, namespace)
        assert mapping == {namespace[urllib.parse.quote("my###Property")]: namespace["myProperty"]}

    def test_create_predicate_mapping_no_namespace(self) -> None:
        properties = [
            InformationInputProperty("myClass", "myProperty", "text", name="my###Property").as_verified(
                default_prefix="my_space"
            )
        ]

        mapping = create_predicate_mapping(properties)
        assert mapping == {urllib.parse.quote("my###Property"): "myProperty"}
