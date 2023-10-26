import tempfile
from copy import deepcopy
from pathlib import Path

import pytest
from rdflib import Graph

from cognite.neat.rules.exceptions import PropertiesDefinedMultipleTimes
from cognite.neat.rules.exporter import OWLExporter, SemanticDataModelExporter, SHACLExporter


def test_rules2owl(transformation_rules):
    file = tempfile.NamedTemporaryFile(suffix=".ttl")
    OWLExporter(rules=transformation_rules, filepath=file.name).export()

    graph = Graph().parse(Path(file.name))
    graph.bind("owl", "http://www.w3.org/2002/07/owl#")
    graph.bind("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")

    # we have 7 classes in the ontology
    assert len(graph.query("SELECT ?s WHERE {?s rdf:type owl:Class Filter (!isBlank(?s))}")) == 7


def test_rules2shacl(transformation_rules):
    file = tempfile.NamedTemporaryFile(suffix=".ttl")
    SHACLExporter(rules=transformation_rules, filepath=file.name).export()
    graph = Graph().parse(Path(file.name))
    graph.bind("owl", "http://www.w3.org/2002/07/owl#")
    graph.bind("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")
    # however we have 6 node shapes since for one class there are no properties defined
    assert len(graph.query("SELECT ?s WHERE {?s rdf:type sh:NodeShape Filter (!isBlank(?s))}")) == 6


def test_rules2semantic_model(transformation_rules):
    file = tempfile.NamedTemporaryFile(suffix=".ttl")
    SemanticDataModelExporter(rules=transformation_rules, filepath=file.name).export()

    graph = Graph().parse(Path(file.name))
    graph.bind("owl", "http://www.w3.org/2002/07/owl#")
    graph.bind("rdf", "http://www.w3.org/1999/02/22-rdf-syntax-ns#")

    assert len(graph.query("SELECT ?s WHERE {?s rdf:type sh:NodeShape Filter (!isBlank(?s))}")) == 6
    assert len(graph.query("SELECT ?s WHERE {?s rdf:type owl:Class Filter (!isBlank(?s))}")) == 7


def test_rules2ontology_raise(transformation_rules):
    file = tempfile.NamedTemporaryFile(suffix=".ttl")
    rules = deepcopy(transformation_rules)
    rules.properties["row 150"] = rules.properties["row 15"]

    with pytest.raises(PropertiesDefinedMultipleTimes):
        OWLExporter(rules=rules, filepath=file.name).export()
