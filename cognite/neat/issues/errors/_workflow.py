from dataclasses import dataclass

from cognite.neat.issues import NeatError


@dataclass(frozen=True)
class InvalidWorkFlowError(NeatError, ValueError):
    """In the workflow step {step_name} the following data is missing: {missing_data}."""

    step_name: str
    missing_data: frozenset[str]


@dataclass(frozen=True)
class StepNotInitializedError(NeatError, RuntimeError):
    """Step {step_name} has not been initialized."""

    step_name: str


@dataclass(frozen=True)
class ConfigurationNotSetError(NeatError, RuntimeError):
    """The configuration variable '{config_variable}' is not set. Please set the configuration
    before running the workflow."""

    config_variable: str


@dataclass(frozen=True)
class InvalidStepOutputError(NeatError, RuntimeError):
    """Object type {step_type} is not supported as step output."""

    step_type: str
