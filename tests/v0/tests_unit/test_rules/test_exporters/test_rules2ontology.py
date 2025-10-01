from pathlib import Path

from rdflib import DCTERMS, OWL, RDF, RDFS, BNode, Graph, Literal, Namespace

from cognite.neat.v0.core._data_model.exporters._data_model2semantic_model import OWLExporter, SHACLExporter
from cognite.neat.v0.core._data_model.models import ConceptualDataModel

SHACL = Namespace("http://www.w3.org/ns/shacl#")


class TestOntologyExporter:
    def test_export_ontology(self, david_rules: ConceptualDataModel, tmp_path: Path) -> None:
        exporter = OWLExporter()
        ttl_path = tmp_path / "test.ttl"

        exporter.export_to_file(david_rules, ttl_path)

        ontology = Graph().parse(ttl_path, format="ttl")

        classes_with_bnodes = set(ontology.subjects(RDF.type, OWL.Class))
        expected_classes = {david_rules.metadata.namespace[concept.concept.suffix] for concept in david_rules.concepts}

        assert expected_classes.issubset(classes_with_bnodes)

        bnodes = classes_with_bnodes - expected_classes
        assert all(isinstance(bnode, BNode) for bnode in bnodes)

        titles = list(ontology.objects(None, DCTERMS.title))
        labels = list(ontology.objects(None, RDFS.label))

        assert 9 == len(labels)
        assert Literal("Generating Unit") in labels

        assert 9 == len(titles)
        assert Literal("GeneratingUnit - Generating Unit") in titles

    def test_export_shacl(self, david_rules: ConceptualDataModel, tmp_path: Path) -> None:
        exporter = SHACLExporter()
        ttl_path = tmp_path / "test.ttl"

        exporter.export_to_file(david_rules, ttl_path)

        shacl_shapes = Graph().parse(ttl_path, format="ttl")
        assert 26 == len(list(shacl_shapes.subjects(RDF.type, SHACL.NodeShape)))
