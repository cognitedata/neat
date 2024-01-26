from datetime import datetime

from rdflib import Namespace

from cognite.neat.rules.models._base import ContainerEntity, ParentClass
from cognite.neat.rules.models.rules import Class, Metadata, Property, Rules
from cognite.neat.rules.models.value_types import XSD_VALUE_TYPE_MAPPINGS


def test_dummy_rules():
    metadata = Metadata(
        name="Dummy Data Model",
        description="A description",
        version="0_1",
        creator="Cognite",
        created=datetime.utcnow(),
        namespace=Namespace("http://purl.org/cognite/neat#"),
        prefix="neat",
    )
    classes = {"DummyClass": Class(class_id="DummyClass", description="A description", parent_class="mega:DummyClass")}
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
    assert rules.metadata.name == "Dummy Data Model"
    assert len(rules.classes) == 2
    assert rules.classes["DummyClass"].parent_class == [
        ParentClass.from_string(entity_string="mega:DummyClass(version=0_1)")
    ]
    assert rules.classes["DummyClass2"].class_id == "DummyClass2"
    assert rules.properties["dummyProperty"].expected_value_type == XSD_VALUE_TYPE_MAPPINGS["string"]
    assert rules.properties["dummyProperty"].container == ContainerEntity.from_string(
        entity_string="outerSpace:DummyClass"
    )
    assert rules.properties["dummyProperty"].container_property == "dummyProperty"
