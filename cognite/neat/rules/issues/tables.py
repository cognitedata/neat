from dataclasses import dataclass

from .base import NeatValidationError


@dataclass(frozen=True)
class NotValidRDFPath(NeatValidationError):
    """Provided `rdfpath` is not valid, i.e. it cannot be converted to SPARQL query.

    Args:
        rdf_path: `rdfpath` that raised exception

    Notes:
        Get familiar with `rdfpath` to avoid this exception.
    """

    description = "Provided `rdfpath` is not valid, i.e. it cannot be converted to SPARQL query"
    fix = "Get familiar with `rdfpath` and check if provided path is valid!"
    rdf_path: str

    def message(self) -> str:
        message = f"{self.rdf_path} is not a valid rdfpath!"

        message += f"\nDescription: {self.description}"
        message += f"\nFix: {self.fix}"
        return message


@dataclass(frozen=True)
class NotValidTableLookUp(NeatValidationError):
    """Provided `table lookup` is not valid, i.e. it cannot be converted to CDF lookup.

    Args:
        table_look_up: `table_look_up`, a part of `rawlookup`, that raised exception

    Notes:
        Get familiar with `rawlookup` and `rdfpath` to avoid this exception.
    """

    description = "Provided table lookup is not valid, i.e. it cannot be converted to CDF lookup"
    fix = "Get familiar with RAW look up and RDF paths and check if provided rawlookup is valid"
    table_look_up: str

    def message(self) -> str:
        message = f"{self.table_look_up} is not a valid table lookup"

        message += f"\nDescription: {self.description}"
        message += f"\nFix: {self.fix}"
        return message


@dataclass(frozen=True)
class NotValidRAWLookUp(NeatValidationError):
    """Provided `rawlookup` is not valid, i.e. it cannot be converted to SPARQL query and CDF lookup

    Args:
        raw_look_up: `rawlookup` rule that raised exception
        verbose: flag that indicates whether to provide enhanced exception message, by default False

    Notes:
        Get familiar with `rawlookup` and `rdfpath` to avoid this exception.
    """

    description = "Provided rawlookup is not valid, i.e. it cannot be converted to SPARQL query and CDF lookup"
    fix = "Get familiar with `rawlookup` and `rdfpath` to avoid this exception"
    raw_look_up: str

    def message(self):
        message = f"Invalid rawlookup expected traversal | table lookup, got {self.raw_look_up}"

        message += f"\nDescription: {self.description}"
        message += f"\nFix: {self.fix}"
        return message
