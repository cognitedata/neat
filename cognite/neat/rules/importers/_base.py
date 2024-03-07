import getpass
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal, overload

from rdflib import Namespace

from cognite.neat.rules._shared import Rules
from cognite.neat.rules.models._rules import RoleTypes, DMSRules, InformationRules
from cognite.neat.rules.validation import IssueList


class BaseImporter(ABC):
    """
    BaseImporter class which all importers inherit from.
    """

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules:
        ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList]:
        ...

    @abstractmethod
    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
        """
        Creates `Rules` object from the data for target role.
        """
        ...

    @classmethod
    def _to_output(cls, rules: Rules, errors: Literal["raise", "continue"] = "continue", role : RoleTypes | None = None) -> tuple[Rules | None, IssueList] | Rules:
        """Converts the rules to the output format."""
        if rules.metadata.role is role or role is None:
            output = rules
        if isinstance(rules, DMSRules) and role is RoleTypes.information_architect:
            output = rules.as_information_architect_rules()
        elif isinstance(rules, InformationRules) and role is RoleTypes.dms_architect:
            output = rules.as_dms_architect_rules()
        else:
            raise NotImplementedError(f"Role {role} is not supported for {type(rules).__name__} rules")

        if errors == "raise":
            return output
        else:
            return output, IssueList()


    def _default_metadata(self):
        return {
            "prefix": "neat",
            "schema": "partial",
            "namespace": Namespace("http://purl.org/cognite/neat/"),
            "version": "0.1.0",
            "title": "Neat Imported Data Model",
            "created": datetime.now().replace(microsecond=0).isoformat(),
            "updated": datetime.now().replace(microsecond=0).isoformat(),
            "creator": getpass.getuser(),
            "description": f"Imported using {type(self).__name__}",
        }
