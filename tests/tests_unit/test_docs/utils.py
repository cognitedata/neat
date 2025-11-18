import textwrap
from pathlib import Path
from typing import cast

from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._utils.auxiliary import get_concrete_subclasses

VALIDATION_DIRECTORY = Path(__file__).parent.resolve(strict=True).parents[2] / "docs" / "validation"


def generate_validation_markdown_docs(validation: type[DataModelValidator]) -> str:
    return textwrap.dedent(cast(str, validation.__doc__))


def write_validation_markdown_docs() -> None:
    validators = get_concrete_subclasses(DataModelValidator)
    for validator in validators:
        doc_content = generate_validation_markdown_docs(validator)
        file_name = f"{validator.__name__}.md"
        file_path = VALIDATION_DIRECTORY / file_name
        file_path.write_text(doc_content, encoding="utf-8")


if __name__ == "__main__":
    write_validation_markdown_docs()
