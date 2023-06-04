from cognite.neat.core.extractors import rules2graph_capturing_sheet
from cognite.neat.core.loader.graph_capturing_sheet import excel_file_to_table_by_name


def test_graph_capturing_sheet(tmp_path, simple_rules, graph_capturing_sheet):
    tmp_sheet = tmp_path / "temp_graph_capturing.xlsx"

    rules2graph_capturing_sheet(simple_rules, tmp_sheet, add_drop_down_list=True, auto_identifier_type="uuid")
    resulting_sheet = excel_file_to_table_by_name(tmp_sheet)
    assert resulting_sheet.keys() == graph_capturing_sheet.keys()
    for sheet_name in resulting_sheet.keys():
        assert list(resulting_sheet[sheet_name].columns) == list(graph_capturing_sheet[sheet_name].columns)
