from cognite.neat.utils.exceptions import NeatError


class InvalidStepOutputException(NeatError):
    type_ = "invalid_step_output"
    code = 400
    description = "The step output is invalid."
    example = "The step output must be a dictionary."

    def __init__(self, step_type: str):
        self.message = f"Object type {step_type} is not supported as step output"
        super().__init__(self.message)


class ConfigurationNotSet(NeatError):
    type_ = "configuration_not_set"
    code = 400
    description = "The configuration is not set."
    example = "The configuration must be set before running the workflow."

    def __init__(self, config_variable: str):
        self.message = (
            f"The configuration variable '{config_variable}' is not set. "
            f"Please set the configuration before running the workflow."
        )
        super().__init__(self.message)

    def __str__(self):
        return self.message


class StepNotInitialized(NeatError):
    def __init__(self, step_name: str):
        self.message = f"Step {step_name} has not been initialized."
        super().__init__(self.message)


class StepFlowContextNotInitialized(NeatError):
    def __init__(self, step_name: str):
        self.message = f"Step {step_name} requires flow context which is missing."
        super().__init__(self.message)
