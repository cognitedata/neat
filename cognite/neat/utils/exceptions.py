from pydantic_core import ErrorDetails, PydanticCustomError


class NeatError(Exception):
    type_: str
    code: int
    description: str
    example: str
    fix: str
    message: str

    def to_pydantic_custom_error(self):
        return PydanticCustomError(
            self.type_,
            self.message,
            dict(type_=self.type_, code=self.code, description=self.description, example=self.example, fix=self.fix),
        )

    def to_error_dict(self) -> ErrorDetails:
        return {
            "type": self.type_,
            "loc": (),
            "msg": self.message,
            "input": None,
            "ctx": dict(
                type_=self.type_,
                code=self.code,
                description=self.description,
                example=self.example,
                fix=self.fix,
            ),
        }


class NeatWarning(UserWarning):
    type_: str
    code: int
    description: str
    example: str
    fix: str
    message: str
