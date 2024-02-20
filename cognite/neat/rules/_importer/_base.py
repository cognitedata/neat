import getpass
from abc import ABC, abstractmethod
from datetime import datetime

from rdflib import Namespace

from cognite.neat.rules.models._rules import DMSRules, DomainRules, InformationRules


class BaseImporter(ABC):
    """
    BaseImporter class which all importers inherit from.
    """

    @abstractmethod
    def to_rules(self) -> DomainRules | InformationRules | DMSRules:
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
