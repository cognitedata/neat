from cognite.neat.utils.exceptions import NeatError


class InvalidStepOutputException(NeatError):
    type_ = "invalid_step_output"
    code = 400
    description = "The step output is invalid."
    example = "The step output must be a dictionary."


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
