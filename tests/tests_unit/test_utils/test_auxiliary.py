import pytest

from cognite.neat._rules.importers import DMSImporter
from cognite.neat.utils.auxiliary import get_classmethods


@pytest.mark.parametrize(
    "cls_, expected_methods",
    [(DMSImporter, [DMSImporter.from_data_model_id, DMSImporter.from_directory, DMSImporter.from_zip_file])],
)
def test_get_classmethods(cls_, expected_methods: list) -> None:
    assert get_classmethods(cls_) == expected_methods
