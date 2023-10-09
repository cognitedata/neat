import pytest

from cognite.neat.rules.importer import owl2excel
from cognite.neat.rules.parser import RawTables, read_excel_file_to_table_by_name
from tests import config


@pytest.fixture(scope="function")
def owl_based_rules() -> RawTables:
    owl2excel(config.WIND_ONTOLOGY)

    return RawTables(**read_excel_file_to_table_by_name(config.WIND_ONTOLOGY.parent / "transformation_rules.xlsx"))


def test_owl2transformation_rules(owl_based_rules: RawTables) -> None:
    raw_tables = owl_based_rules
    assert raw_tables.Metadata.iloc[0, 1] == "https://kg.cognite.ai/wind/"
    assert len(set(raw_tables.Classes.Class.values)) == 68
