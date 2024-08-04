from dataclasses import dataclass

from cognite.neat.issues import NeatError


@dataclass(frozen=True)
class WorkFlowMissingDataError(NeatError, ValueError):
    """In the workflow step {step_name} the following data is missing: {missing_data}."""

    step_name: str
    missing_data: frozenset[str]


@dataclass(frozen=True)
class WorkflowStepNotInitializedError(NeatError, RuntimeError):
    """Step {step_name} has not been initialized."""

    step_name: str


@dataclass(frozen=True)
class WorkflowConfigurationNotSetError(NeatError, RuntimeError):
    """The configuration variable '{config_variable}' is not set. Please set the configuration
    before running the workflow."""

    config_variable: str


@dataclass(frozen=True)
class WorkflowStepOutputError(NeatError, RuntimeError):
    """Object type {step_type} is not supported as step output.

    Step output must be of type DataContract or a FlowMessage.
    """

    step_type: str
