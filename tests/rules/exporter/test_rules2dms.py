from datetime import datetime

import pytest
from rdflib import Namespace

from cognite.neat.rules.exceptions import EntitiesContainNonDMSCompliantCharacters
from cognite.neat.rules.exporter._rules2dms import DataModel
from cognite.neat.rules.models._base import ParentClass
from cognite.neat.rules.models.rules import Class, Metadata, Property, Rules


def test_rules2dms_single_space(simple_rules):
    data_model = DataModel.from_rules(rules=simple_rules)

    assert len(data_model.containers) == 4
    assert len(data_model.views) == 4
    assert list(data_model.views.keys()) == [
        "neat:CountryGroup",
        "neat:Country",
        "neat:PriceArea",
        "neat:PriceAreaConnection",
    ]
    assert list(data_model.containers.keys()) == [
        "neat:CountryGroup",
        "neat:Country",
        "neat:PriceArea",
        "neat:PriceAreaConnection",
    ]
    assert data_model.version == "0.1"
    assert data_model.space == "neat"
    assert data_model.external_id == "playground_model"


def test_rules2dms_multi_space():
    metadata = Metadata(
        name="Dummy Data Model",
        description="A description",
        version="0.1",
        creator="Cognite",
        created=datetime.utcnow(),
        namespace=Namespace("http://purl.org/cognite/neat#"),
        prefix="neat",
    )
    classes = {
        "DummyClass": Class(class_id="DummyClass", description="A description", parent_class="mega:DummyClass"),
        "EmptyClass": Class(class_id="EmptyClass"),
    }
    properties = {
        "dummyProperty": Property(
            class_id="DummyClass2",
            property_id="dummyProperty",
            expected_value_type="string",
            max_count=1,
            container="outerSpace:DummyClass",
        )
    }

    # Act
    rules = Rules(metadata=metadata, classes=classes, properties=properties, prefixes={}, instances=[])

    data_model = DataModel.from_rules(rules=rules)
    assert len(data_model.containers) == 1
    assert len(data_model.views) == 2
    assert list(data_model.views.keys()) == [
        "neat:DummyClass",
        "neat:DummyClass2",
    ]
    assert list(data_model.containers.keys()) == [
        "outerSpace:DummyClass",
    ]

    assert data_model.views["neat:DummyClass"].implements == [
        ParentClass.from_string(entity_string="mega:DummyClass(version=0.1)").view_id
    ]


def test_raise_error10(transformation_rules):
    with pytest.raises(EntitiesContainNonDMSCompliantCharacters):
        _ = DataModel.from_rules(rules=transformation_rules)


def test_raise_container_error():
    metadata = Metadata(
        name="Dummy Data Model",
        description="A description",
        version="0.1",
        creator="Cognite",
        created=datetime.utcnow(),
        namespace=Namespace("http://purl.org/cognite/neat#"),
        prefix="neat",
    )
    classes = {
        "DummyClass": Class(class_id="DummyClass", description="A description", parent_class="mega:DummyClass"),
        "EmptyClass": Class(class_id="EmptyClass"),
    }
    properties = {
        "dummyProperty": Property(
            class_id="DummyClass2",
            property_id="dummyProperty",
            expected_value_type="string",
            max_count=1,
            container="outerSpace:DummyClass",
        ),
        "dummyProperty2": Property(
            class_id="DummyClass2",
            property_id="dummyProperty",
            expected_value_type="float",
            max_count=1,
            container="outerSpace:DummyClass",
        ),
    }

    # Act
    rules = Rules(metadata=metadata, classes=classes, properties=properties, prefixes={}, instances=[])

    with pytest.raises(ExceptionGroup) as exc_info:
        _ = DataModel.from_rules(rules=rules)
    assert exc_info.value.message == "Properties value types have been redefined! This is prohibited! Aborting!"
    assert "Container outerSpace:DummyClass property dummyProperty value type" in exc_info.value.exceptions[0].message


def test_raise_view_error():
    metadata = Metadata(
        name="Dummy Data Model",
        description="A description",
        version="0.1",
        creator="Cognite",
        created=datetime.utcnow(),
        namespace=Namespace("http://purl.org/cognite/neat#"),
        prefix="neat",
    )
    classes = {
        "DummyClass": Class(class_id="DummyClass", description="A description", parent_class="mega:DummyClass"),
        "EmptyClass": Class(class_id="EmptyClass"),
    }
    properties = {
        "dummyProperty": Property(
            class_id="DummyClass2",
            property_id="dummyProperty",
            expected_value_type="string",
            max_count=1,
            container="outerSpace:DummyClass",
        ),
        "dummyProperty2": Property(
            class_id="DummyClass2",
            property_id="dummyProperty",
            expected_value_type="float",
            max_count=1,
            container="outerSpace:DummyClass",
            container_property="dummyProperty2",
        ),
    }

    # Act
    rules = Rules(metadata=metadata, classes=classes, properties=properties, prefixes={}, instances=[])

    with pytest.raises(ExceptionGroup) as exc_info:
        _ = DataModel.from_rules(rules=rules)
    assert exc_info.value.message == "View properties have been redefined! This is prohibited! Aborting!"
    assert (
        "View neat:DummyClass2 property dummyProperty has been redefined in the same view"
        in exc_info.value.exceptions[0].message
    )
