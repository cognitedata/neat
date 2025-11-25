import importlib
import re

import pytest
import yaml

from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._utils.auxiliary import get_concrete_subclasses
from tests.tests_unit.test_docs import generate_docs
from tests.tests_unit.test_docs.generate_docs import (
    ENCODING,
    MKDOCS_FILE,
    VALIDATION_DIRECTORY,
    VALIDATION_INDEX_MD,
    generate_validation_index_markdown_docs,
    generate_validation_markdown_docs,
    get_filename,
    get_validator_group_heading,
)

RUN_SCRIPT = f"python {generate_docs.__file__}"


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
        if actual_content.endswith("\n"):
            actual_content = actual_content[:-1]
        assert actual_content == expected_content, (
            f"The validation markdown documentation for {validator_cls.__name__} is out of date. "
            "Please run the documentation generation script to update it:\n\n"
            f"{RUN_SCRIPT}\n"
        )

    def test_nav_var_is_up_to_date(self) -> None:
        mkdocs_file = yaml.safe_load(MKDOCS_FILE.read_text(encoding=ENCODING))
        try:
            nav_list = mkdocs_file["nav"]
            validation_list = next(item["Validations"] for item in nav_list if "Validations" in item)
        except (KeyError, TypeError, StopIteration):
            raise AssertionError(
                "The mkdocs.yml file is missing the 'Validations' section in the 'nav' configuration."
            ) from None
        module_names = sorted(
            {validator_cls.__module__ for validator_cls in get_concrete_subclasses(DataModelValidator)}
        )
        modules = [importlib.import_module(module_name) for module_name in module_names]
        expected_validation_groups: list[dict[str, str]] = []
        for module in modules:
            heading = get_validator_group_heading(module)
            display_name = heading
            # Replace non-word characters with hyphens, strip leading/trailing hyphens, and convert to lowercase
            url = re.sub(r"[^\w]+", "-", display_name).strip("-").lower()
            expected_validation_groups.append({display_name: f"validation/index.html#{url}"})

        assert validation_list == expected_validation_groups, (
            "The 'Validations' section in mkdocs.yml is out of date. "
            "This must be manually updated with the new validator groups."
        )
