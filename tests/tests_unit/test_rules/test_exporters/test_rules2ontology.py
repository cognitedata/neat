from pathlib import Path

from rdflib import DCTERMS, RDF, RDFS, Graph, Literal, Namespace

from cognite.neat.core._data_model.exporters._data_model2ontology import SemanticDataModelExporter
from cognite.neat.core._data_model.models import ConceptualDataModel

SHACL = Namespace("http://www.w3.org/ns/shacl#")


class TestOntologyExporter:
    def test_export_semantic_data_model(self, david_rules: ConceptualDataModel, tmp_path: Path) -> None:
        exporter = SemanticDataModelExporter()
        ttl_path = tmp_path / "test.ttl"

        exporter.export_to_file(david_rules, ttl_path)

        semantic_dm = Graph().parse(ttl_path, format="ttl")
        assert 26 == len(list(semantic_dm.subjects(RDF.type, SHACL.NodeShape)))

        titles = list(semantic_dm.objects(None, DCTERMS.title))
        labels = list(semantic_dm.objects(None, RDFS.label))

        assert 9 == len(labels)
        assert Literal("Generating Unit") in labels

        assert 9 == len(titles)
        assert Literal("GeneratingUnit - Generating Unit") in titles
