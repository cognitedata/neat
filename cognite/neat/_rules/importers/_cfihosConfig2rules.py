"""This module performs importing of graph to TransformationRules pydantic class.
In more details, it traverses the graph and abstracts class and properties, basically
generating a list of rules based on which nodes that form the graph are made.
"""

from collections import UserDict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import pandas as pd
from pandas import ExcelFile

from cognite.neat._cfihos.processing.base_starter import base_starter_class
from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import (
    FileMissingRequiredFieldError,
    FileNotFoundNeatError,
)
from cognite.neat._rules._shared import ReadRules, T_InputRules
from cognite.neat._rules.models import (
    INPUT_RULES_BY_ROLE,
    RoleTypes,
    SchemaCompleteness,
)

from ._base import BaseImporter


@dataclass
class ReadResult:
    Properties: list[dict]
    Containers: list[dict]
    Views: list[dict]
    Metadata: dict


class MetadataRaw(UserDict):
    @classmethod
    def from_config(cls, excel_file: ExcelFile, metadata_sheet_name: str) -> "MetadataRaw":
        return cls(pd.read_excel(excel_file, metadata_sheet_name, header=None).replace(float("nan"), None).values)

    @property
    def has_role_field(self) -> bool:
        return self.get("role") in [role.value for role in RoleTypes.__members__.values()]

    @property
    def role(self) -> RoleTypes:
        return RoleTypes(self["role"])

    @property
    def has_schema_field(self) -> bool:
        return self.get("schema") in [schema.value for schema in SchemaCompleteness.__members__.values()]

    @property
    def schema(self) -> SchemaCompleteness | None:
        if not self.has_schema_field:
            return None
        return SchemaCompleteness(self["schema"])

    def is_valid(self, issue_list: IssueList, filepath: Path) -> bool:
        if not self.has_role_field:
            issue_list.append(FileMissingRequiredFieldError(filepath, "metadata", "role"))
            return False

        return True


class CFIHOSReader:
    def __init__(
        self,
        # issue_list: IssueList,
        required: bool = True,
        sheet_prefix: Literal["", "Last", "Ref", "CDMRef"] = "",
    ):
        # self.issue_list = issue_list
        self.required = required
        self._sheet_prefix = sheet_prefix
        self._seen_files: set[Path] = set()
        self._seen_sheets: set[str] = set()

    @property
    def metadata_sheet_name(self) -> str:
        return f"{self._sheet_prefix}Metadata"

    @property
    def prefixes_sheet_name(self) -> str:
        return "Prefixes"

    @property
    def seen_sheets(self) -> set[str]:
        if not self._seen_files:
            raise ValueError("No files have been read yet.")
        return self._seen_sheets

    def read(self, filepath: Path) -> None | ReadResult:  # TODO: the return should be an objetct lke ReadReslut
        self._seen_files.add(filepath)

        filePath = str(filepath)  # TODO: this is a temp solution. path should be a path object and pass to processor
        cfihos_starter = base_starter_class(filePath)
        sheets = cfihos_starter.process_model()

        # cfihosResult = ReadResult(Properties=sheets["Properties"], Containers=sheets["Containers"], Views=sheets["Views"], Metadata=sheets["Metadata"])

        return sheets


class CFIHOSImporter(BaseImporter[T_InputRules]):
    """Import rules from an Excel file.

    Args:
        filepath (Path): The path to the Excel file.
    """

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_rules(self) -> ReadRules[T_InputRules]:
        # issue_list = IssueList(title=f"'{self.filepath.name}'") TODO: implement issueList as Excel reader to validate the format of CFIHOS csv/excel files
        if not self.filepath.exists():
            raise FileNotFoundNeatError(self.filepath)

        user_reader = CFIHOSReader()

        cfihos_read = user_reader.read(self.filepath)

        # issue_list.trigger_warnings()
        # if issue_list.has_errors:
        #     raise MultiValueError(issue_list.errors)

        if cfihos_read is None:
            return ReadRules(None, {})

        # TODO: refactor this to be as _spreadsheet2rules
        # sheets = cfihos_read
        # original_role = user_read.role

        rules_cls = INPUT_RULES_BY_ROLE[RoleTypes.dms]
        rules = cast(T_InputRules, rules_cls.load(cfihos_read))
        return ReadRules(rules, {})
