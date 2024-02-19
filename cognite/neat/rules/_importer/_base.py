import getpass
from abc import ABC, abstractmethod
from datetime import datetime

from cognite.neat.rules.models._rules import DomainRules, InformationRules


class BaseImporter(ABC):
    """
    BaseImporter class which all importers inherit from.
    """

    @abstractmethod
    def __init__(self):
        ...

    @abstractmethod
    def to_rules(self, *args, **kwargs) -> DomainRules | InformationRules:
        """
        Creates `Rules` object from the data for target role.
        """
        ...

    def _default_metadata(self):
        return {
            "prefix": "neat",
            "version": "0.1.0",
            "title": "Neat Imported Data Model",
            "created": datetime.now().replace(microsecond=0).isoformat(),
            "creator": getpass.getuser(),
            "description": f"Imported using {type(self).__name__}",
        }
