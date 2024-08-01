from cognite.neat.exceptions import NeatException


class InvalidStepOutputException(NeatException):
    type_ = "invalid_step_output"
    code = 400
    description = "The step output is invalid."
    example = "The step output must be a dictionary."

    def __init__(self, step_type: str):
        self.message = f"Object type {step_type} is not supported as step output"
        super().__init__(self.message)
