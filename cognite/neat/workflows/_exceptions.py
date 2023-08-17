from cognite.neat.utils.exceptions import NeatError


class InvalidStepOutputException(NeatError):
    type_ = "invalid_step_output"
    code = 400
    description = "The step output is invalid."
    example = "The step output must be a dictionary."
