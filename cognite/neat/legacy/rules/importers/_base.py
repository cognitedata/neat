import getpass
from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd
from pydantic_core import ErrorDetails

from cognite.neat.legacy.rules.models.raw_rules import RawRules
from cognite.neat.legacy.rules.models.rules import Rules


class BaseImporter(ABC):
    """
    BaseImporter class which all importers inherit from.
    """

    @abstractmethod
    def to_tables(self) -> dict[str, pd.DataFrame]:
        """Creates raw tables from the data."""
        raise NotImplementedError

    def to_raw_rules(self) -> RawRules:
        """Creates `RawRules` object from the data."""

        tables = self.to_tables()

        return RawRules.from_tables(tables=tables, importer_type=self.__class__.__name__)

    def to_rules(
        self,
        return_report: bool = False,
        skip_validation: bool = False,
        validators_to_skip: set[str] | None = None,
    ) -> tuple[Rules | None, list[ErrorDetails] | None, list | None] | Rules:
        """
        Creates `Rules` object from the data.

        Args:
            return_report: To return validation report. Defaults to False.
            skip_validation: Bypasses Rules validation. Defaults to False.
            validators_to_skip: List of validators to skip. Defaults to None.

        Returns:
            Instance of `Rules`, which can be validated, not validated based on
            `skip_validation` flag, or partially validated if `validators_to_skip` is set,
            and optional list of errors and warnings if
            `return_report` is set to True.

        !!! Note "Skip Validation
            `skip_validation` flag should be only used for purpose when `Rules` object
            is exported to an Excel file. Do not use this flag for any other purpose!
        """

        raw_rules = self.to_raw_rules()

        return raw_rules.to_rules(return_report, skip_validation, validators_to_skip)

    def _default_metadata(self):
        return {
            "prefix": "neat",
            "version": "0.1.0",
            "title": "Neat Imported Data Model",
            "created": datetime.now().replace(microsecond=0).isoformat(),
            "creator": getpass.getuser(),
            "description": f"Imported using {type(self).__name__}",
        }
