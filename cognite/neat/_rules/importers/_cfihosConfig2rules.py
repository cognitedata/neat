"""This module performs importing of graph to TransformationRules pydantic class.
In more details, it traverses the graph and abstracts class and properties, basically
generating a list of rules based on which nodes that form the graph are made.
"""

from collections import UserDict, defaultdict
from dataclasses import dataclass
import io
from pathlib import Path
from typing import Literal, cast

import pandas as pd
from cognite.client.utils._importing import local_import
from pandas import ExcelFile
from rdflib import Namespace, URIRef

from cognite.neat._issues import IssueList, MultiValueError
from cognite.neat._issues.errors import (
    FileMissingRequiredFieldError,
    FileNotFoundNeatError,
    FileReadError,
)
from cognite.neat._issues.warnings import FileMissingRequiredFieldWarning
from cognite.neat._rules._shared import ReadRules, T_InputRules
from cognite.neat._rules.models import (
    INPUT_RULES_BY_ROLE,
    VERIFIED_RULES_BY_ROLE,
    RoleTypes,
    SchemaCompleteness,
)
from cognite.neat._utils.reader._base import NeatReader
from cognite.neat._utils.spreadsheet import SpreadsheetRead, read_individual_sheet
from cognite.neat._utils.text import humanize_collection

from ._base import BaseImporter
from _cfihos.processing import base_starter
from _cfihos.processing.base_starter import base_starter_class

class CFIHOSReader:
    def __init__(
        self,
        issue_list: IssueList,
        required: bool = True,
        sheet_prefix: Literal["", "Last", "Ref", "CDMRef"] = "",
    ):
        self.issue_list = issue_list
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


    def read(self, filepath: Path) -> None | dict: #TODO: the return should be an objetct lke ReadReslut
        self._seen_files.add(filepath)

        filePath = NeatReader.create(io).materialize_path()
        sheets =  base_starter_class.process_model(filePath)
  
        return sheets

class CFIHOSImporter(BaseImporter[T_InputRules]):
    """Import rules from an Excel file.

    Args:
        filepath (Path): The path to the Excel file.
    """

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def to_rules(self) -> ReadRules[T_InputRules]:
        issue_list = IssueList(title=f"'{self.filepath.name}'")
        if not self.filepath.exists():
            raise FileNotFoundNeatError(self.filepath)

        with pd.ExcelFile(self.filepath) as excel_file:
            user_reader = CFIHOSReader(issue_list)

            user_read = user_reader.read(excel_file, self.filepath)

        issue_list.trigger_warnings()
        if issue_list.has_errors:
            raise MultiValueError(issue_list.errors)

        if user_read is None:
            return ReadRules(None, {})

        sheets = user_read.sheets
        original_role = user_read.role
        read_info_by_sheet = user_read.read_info_by_sheet

        rules_cls = INPUT_RULES_BY_ROLE[original_role]
        rules = cast(T_InputRules, rules_cls.load(sheets))
        return ReadRules(rules, read_info_by_sheet)
