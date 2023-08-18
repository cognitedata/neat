import pytest
from cognite.neat.rules.exporter.rules2ontology import Ontology
from cognite.neat.rules.exceptions import PropertiesDefinedMultipleTimes
from copy import deepcopy


def test_rules2ontology(transformation_rules):
    ontology = Ontology.from_rules(transformation_rules)

    # we have 7 classes in the ontology
    assert len(ontology.as_owl().query("SELECT ?s WHERE {?s rdf:type owl:Class Filter (!isBlank(?s))}")) == 7
    # however we have 6 node shapes since for one class there are no properties defined
    assert len(ontology.as_shacl().query("SELECT ?s WHERE {?s rdf:type sh:NodeShape Filter (!isBlank(?s))}")) == 6


def test_rules2ontology_raise(transformation_rules):
    rules = deepcopy(transformation_rules)
    rules.properties["row 150"] = rules.properties["row 15"]

    with pytest.raises(PropertiesDefinedMultipleTimes):
        _ = Ontology.from_rules(rules)
