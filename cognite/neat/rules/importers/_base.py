import getpass
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Literal, TypeAlias, overload

from rdflib import Namespace

from cognite.neat.rules.models._rules import DMSRules, DomainRules, InformationRules

from ._models import IssueList

Rule: TypeAlias = DomainRules | InformationRules | DMSRules | None


class BaseImporter(ABC):
    """
    BaseImporter class which all importers inherit from.
    """

    @overload
    def to_rules(self, errors: Literal["raise"]) -> Rule:
        ...

    @overload
    def to_rules(self, errors: Literal["continue"]) -> tuple[Rule | None, IssueList]:
        ...

    @abstractmethod
    def to_rules(self, errors: Literal["raise", "continue"]) -> tuple[Rule | None, IssueList] | Rule:
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
