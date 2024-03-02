from pathlib import Path

from rdflib import RDF, Graph, Namespace

from cognite.neat.rules.exporters._rules2ontology import SemanticDataModelExporter
from cognite.neat.rules.models._rules import InformationRules

SHACL = Namespace("http://www.w3.org/ns/shacl#")


class TestOntologyExporter:
    def test_export_semantic_data_model(self, david_rules: InformationRules, tmp_path: Path) -> None:
        exporter = SemanticDataModelExporter(rules=david_rules)
        ttl_path = tmp_path / "test.ttl"

        exporter.export_to_file(ttl_path)

        semantic_dm = Graph().parse(ttl_path, format="ttl")
        assert 26 == len(list(semantic_dm.subjects(RDF.type, SHACL.NodeShape)))
