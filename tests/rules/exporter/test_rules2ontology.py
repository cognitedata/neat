from copy import deepcopy

import pytest

from cognite.neat.rules.exceptions import PropertiesDefinedMultipleTimes
from cognite.neat.rules.exporter import OWLExporter, SemanticDataModelExporter, SHACLExporter


def test_rules2owl(transformation_rules):
    owl_exporter = OWLExporter(rules=transformation_rules, filepath=None)

    # we have 7 classes in the ontology
    assert len(owl_exporter.data.query("SELECT ?s WHERE {?s rdf:type owl:Class Filter (!isBlank(?s))}")) == 7


def test_rules2shacl(transformation_rules):
    shacl_exporter = SHACLExporter(rules=transformation_rules, filepath=None)

    # however we have 6 node shapes since for one class there are no properties defined
    assert len(shacl_exporter.data.query("SELECT ?s WHERE {?s rdf:type sh:NodeShape Filter (!isBlank(?s))}")) == 6


def test_rules2semantic_model(transformation_rules):
    semantic_model_exporter = SemanticDataModelExporter(rules=transformation_rules, filepath=None)

    # however we have 6 node shapes since for one class there are no properties defined
    assert (
        len(semantic_model_exporter.data.query("SELECT ?s WHERE {?s rdf:type sh:NodeShape Filter (!isBlank(?s))}")) == 6
    )
    assert len(semantic_model_exporter.data.query("SELECT ?s WHERE {?s rdf:type owl:Class Filter (!isBlank(?s))}")) == 7


def test_rules2ontology_raise(transformation_rules):
    rules = deepcopy(transformation_rules)
    rules.properties["row 150"] = rules.properties["row 15"]

    with pytest.raises(PropertiesDefinedMultipleTimes):
        OWLExporter(rules=rules, filepath=None)
