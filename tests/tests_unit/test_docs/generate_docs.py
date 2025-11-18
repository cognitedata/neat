import importlib
import inspect
import itertools
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from cognite.neat._data_model.validation.dms._base import DataModelValidator
from cognite.neat._utils.auxiliary import get_concrete_subclasses

NEAT_DIRECTORY = Path(__file__).parent.resolve(strict=True).parents[2]
MKDOCS_FILE = NEAT_DIRECTORY / "mkdocs.yml"
VALIDATION_DIRECTORY = NEAT_DIRECTORY / "docs" / "validation"
VALIDATION_INDEX_MD = VALIDATION_DIRECTORY / "index.md"

ENCODING = "utf-8"
NEWLINE = "\n"


@dataclass(order=True)
class Validator:
    module_name: str
    code: str
    cls: type[DataModelValidator]


def generate_validation_markdown_docs(validation: type[DataModelValidator]) -> str:
    return inspect.cleandoc(validation.__doc__ or "")


def get_filename(validation: type[DataModelValidator]) -> str:
    return f"{validation.code.casefold()}.md"


def write_validation_markdown_docs() -> int:
    count = 0
    for validator in get_concrete_subclasses(DataModelValidator):
        doc_content = generate_validation_markdown_docs(validator)
        file_path = VALIDATION_DIRECTORY / get_filename(validator)
        file_path.write_text(doc_content, encoding=ENCODING, newline=NEWLINE)
        count += 1
    return count


def get_validator_group_heading(module: ModuleType) -> str:
    if not hasattr(module, "BASE_CODE"):
        raise NotImplementedError(f"Module {module.__name__} is missing BASE_CODE attribute.")
    module_display_name = module.__name__.rsplit(".", maxsplit=1)[-1].removeprefix("_").title()
    return f"{module_display_name} ({module.BASE_CODE})"


def generate_validation_index_markdown_docs() -> str:
    validators = [
        Validator(validator_cls.__module__, validator_cls.code, validator_cls)
        for validator_cls in get_concrete_subclasses(DataModelValidator)
    ]
    lines: list[
        str
    ] = f"""**Neat supports {len(validators)} validation rules** for data modeling. These rules are learned
 from best practice, knowledge of the Cognite Data Fusion data modeling service, and practical experience from
 helping customers build and maintain their data models.
""".split("\n")
    lines.append("")
    lines.append("")

    for module_name, validator_group in itertools.groupby(sorted(validators), key=lambda v: v.module_name):
        module = importlib.import_module(module_name)
        heading = get_validator_group_heading(module)
        lines.append(f"### {heading}")
        lines.append("")
        if module.__doc__ is None:
            raise NotImplementedError(f"Module {module_name} is missing a docstring.")
        lines.append(module.__doc__)
        lines.append("")
        lines.append("| code | name | message |")
        lines.append("|------|------|---------|")
        for validator in validator_group:
            code = validator.cls.code
            name = validator.cls.__name__
            if validator.cls.__doc__ is None:
                raise NotImplementedError(f"Validator {name} is missing a docstring.")
            message = validator.cls.__doc__.strip().splitlines()[0]
            filename = get_filename(validator.cls)
            lines.append(f"| {code} | [{name}]({filename}) | {message} |")
        lines.append("")

    return "\n".join(lines)


def write_validation_index_markdown_docs() -> None:
    index_content = generate_validation_index_markdown_docs()
    VALIDATION_INDEX_MD.write_text(index_content, encoding=ENCODING, newline=NEWLINE)


if __name__ == "__main__":
    written = write_validation_markdown_docs()
    print(f"Wrote {written} validation markdown docs.")
    write_validation_index_markdown_docs()
    print("Wrote validation index markdown doc.")
