from cognite.neat.graph import extractor as graph_extractor
from cognite.neat.graph.extractor._graph_capturing_sheet import rules2graph_capturing_sheet
from cognite.neat.rules.importer import ExcelImporter
from tests import config


def test_graph_capturing_sheet(tmp_path, simple_rules):
    extractor = graph_extractor.GraphCapturingSheet(
        simple_rules, config.GRAPH_CAPTURING_SHEET, store_graph_capturing_sheet=True
    )
    _ = extractor.extract()
    graph_capturing_sheet = extractor.sheet
    tmp_sheet = tmp_path / "temp_graph_capturing.xlsx"

    rules2graph_capturing_sheet(simple_rules, tmp_sheet, add_drop_down_list=True, auto_identifier_type="uuid")
    resulting_sheet = ExcelImporter(tmp_sheet).to_tables()
    assert resulting_sheet.keys() == graph_capturing_sheet.keys()
    for sheet_name in resulting_sheet.keys():
        assert list(resulting_sheet[sheet_name].columns) == list(graph_capturing_sheet[sheet_name].columns)
