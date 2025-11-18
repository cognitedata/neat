import pytest

import tests.tests_unit.test_docs.utils
from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from tests.tests_unit.test_docs.utils import (
    ENCODING,
    VALIDATION_DIRECTORY,
    VALIDATION_INDEX_MD,
    generate_validation_index_markdown_docs,
    generate_validation_markdown_docs,
    get_filename,
)

RUN_SCRIPT = f"python {tests.tests_unit.test_docs.utils.__file__}"


class TestValidationDocs:
    def test_index_md_is_up_to_date(self) -> None:
        expected_content = generate_validation_index_markdown_docs()
        actual_content = VALIDATION_INDEX_MD.read_text(encoding=ENCODING)
        assert actual_content == expected_content, (
            "The validation index markdown documentation is out of date. "
            "Please run the documentation generation script to update it:\n\n"
            f"{RUN_SCRIPT}\n"
        )

    @pytest.mark.parametrize("validator_cls", get_concrete_subclasses(DataModelValidator))
    def test_validation_md_is_up_to_date(self, validator_cls: type[DataModelValidator]) -> None:
        expected_content = generate_validation_markdown_docs(validator_cls)
        file_path = VALIDATION_DIRECTORY / get_filename(validator_cls)
        actual_content = file_path.read_text(encoding=ENCODING)
        assert actual_content == expected_content, (
            f"The validation markdown documentation for {validator_cls.__name__} is out of date. "
            "Please run the documentation generation script to update it:\n\n"
            f"{RUN_SCRIPT}\n"
        )
