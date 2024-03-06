import getpass
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal, TypeAlias, overload

from rdflib import Namespace

from cognite.neat.rules.models._rules import DMSRules, DomainRules, InformationRules, RoleTypes
from cognite.neat.rules.validation import IssueList

Rules: TypeAlias = DomainRules | InformationRules | DMSRules


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

    def _default_metadata(self):
        return {
            "prefix": "neat",
            "namespace": Namespace("http://purl.org/cognite/neat/"),
            "version": "0.1.0",
            "title": "Neat Imported Data Model",
            "created": datetime.now().replace(microsecond=0).isoformat(),
            "updated": datetime.now().replace(microsecond=0).isoformat(),
            "creator": getpass.getuser(),
            "description": f"Imported using {type(self).__name__}",
        }
