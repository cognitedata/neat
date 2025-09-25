from typing import Any, ClassVar

import pytest

from cognite.neat.v0.core._data_model.importers import DMSImporter
from cognite.neat.v0.core._utils.auxiliary import (
    get_classmethods,
    get_parameters_by_method,
)


@pytest.mark.parametrize(
    "cls_, expected_methods",
    [
        (
            DMSImporter,
            [
                DMSImporter.as_unverified_concept,
                DMSImporter.as_unverified_conceptual_property,
                DMSImporter.from_data_model,
                DMSImporter.from_data_model_id,
                DMSImporter.from_directory,
                DMSImporter.from_path,
                DMSImporter.from_zip_file,
            ],
        )
    ],
)
def test_get_classmethods(cls_, expected_methods: list) -> None:
    assert get_classmethods(cls_) == expected_methods


class SubClass:
    def verify(self) -> None: ...

    def do_something(self, a: int, b: bool) -> None: ...

    @property
    def also_ignore_me(self) -> str: ...

    def __call__(self, io: Any) -> None: ...


class MyClass:
    ignore_me: ClassVar[str] = "ignore"

    def __init__(self) -> None:
        self.sub_class = SubClass()

    def action(self, values: tuple[int, ...]) -> None: ...


@pytest.mark.parametrize(
    "type_, expected_methods",
    [
        (
            MyClass,
            {
                "action": {"values": tuple[int, ...]},
                "sub_class.verify": {},
                "sub_class.do_something": {"a": int, "b": bool},
                "sub_class.__call__": {"io": Any},
            },
        )
    ],
)
def test_get_parameters_by_method(type_: type, expected_methods: dict[str, dict[str, type]]) -> None:
    obj = type_()
    assert get_parameters_by_method(obj) == expected_methods
