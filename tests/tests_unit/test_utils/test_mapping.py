import urllib.parse

from rdflib import Namespace

from cognite.neat._rules.models.information import InformationInputClass, InformationInputProperty
from cognite.neat._utils.mapping import create_predicate_mapping, create_type_mapping


class TestCreateTypeMapping:
    def test_create_predicate_mapping(self) -> None:
        namespace = Namespace("http://example.org/")
        classes = [InformationInputClass("MyType", name="my$$$Type").as_verified(default_prefix="my_space")]
        mapping = create_type_mapping(classes, namespace)
        assert mapping == {namespace[urllib.parse.quote("my$$$Type")]: namespace["MyType"]}


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
