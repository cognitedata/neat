from dataclasses import dataclass

from cognite.neat.issues import NeatError
from cognite.neat.utils.text import humanize_sequence


@dataclass(frozen=True)
class InvalidWorkFlowError(NeatError, ValueError):
    """In the workflow step {step_name} the following data is missing: {missing_data}."""

    step_name: str
    missing_data: frozenset[str]

    def dump(self) -> dict[str, str]:
        output = super().dump()
        output["stepName"] = self.step_name
        output["missingData"] = self.missing_data
        return output

    def message(self) -> str:
        return (self.__doc__ or "").format(
            step_name=self.step_name, missing_data=humanize_sequence(list(self.missing_data))
        )


@dataclass(frozen=True)
class StepNotInitialized(NeatError, RuntimeError):
    """Step {step_name} has not been initialized."""

    step_name: str

    def dump(self) -> dict[str, str]:
        output = super().dump()
        output["stepName"] = self.step_name
        return output

    def message(self) -> str:
        return (self.__doc__ or "").format(step_name=self.step_name)


@dataclass(frozen=True)
class ConfigurationNotSet(NeatError, RuntimeError):
    """The configuration variable '{config_variable}' is not set. Please set the configuration
    before running the workflow."""

    config_variable: str

    def dump(self) -> dict[str, str]:
        output = super().dump()
        output["configVariable"] = self.config_variable
        return output

    def message(self) -> str:
        return (self.__doc__ or "").format(config_variable=self.config_variable)
