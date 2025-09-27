from typing import Any

from pydantic import Field, model_validator

from cognite.neat._data_model.models.entities import URI, ConceptEntity, DataType, UnknownEntity

from ._base import ResourceMetadata


class Property(ResourceMetadata):
    value_type: DataType | ConceptEntity | UnknownEntity = Field(
        union_mode="left_to_right",
        description="Value type that the property can hold. It takes either subset of XSD type or a class defined.",
    )
    min_count: int | None = Field(
        default=None,
        ge=0,
        description="Minimum number of values that the property can hold. "
        "If no value is provided, the default value is None meaning `0`, "
        "which means that the property is optional.",
    )
    max_count: int | None = Field(
        default=None,
        ge=0,
        description="Maximum number of values that the property can hold. "
        "If no value is provided, the default value is None meaning `inf`, "
        "which means that the property can hold any number of values (listable).",
    )
    default: Any | None = Field(alias="Default", default=None, description="Default value of the property.")
    instance_reference: list[URI] | None = Field(
        default=None,
        description="The URI(s) in the graph to get the value of the property.",
    )

    @model_validator(mode="after")
    def check_min_max_count(self) -> "Property":
        if self.min_count is not None and self.max_count is not None:
            if self.min_count > self.max_count:
                raise ValueError("min_count must be less than or equal to max_count")
        return self

    @model_validator(mode="after")
    def check_default_value_primitive_type(self) -> "Property":
        if not self.default:
            return self

        if not isinstance(self.value_type, DataType):
            raise ValueError("Setting default value is only supported for primitive value types.")
        return self

    @model_validator(mode="after")
    def check_default_value_python_type_exists(self) -> "Property":
        if not self.default:
            return self

        if isinstance(self.value_type, DataType) and not hasattr(self.value_type, "python"):
            raise ValueError(
                f"DataType {self.value_type} does not have a python type defined."
                " Setting default value for property is not possible."
            )
        return self

    @model_validator(mode="after")
    def check_default_value_not_list(self) -> "Property":
        if not self.default:
            return self

        if isinstance(self.default, list):
            raise ValueError("Setting list as default value is not supported.")
        return self

    @model_validator(mode="after")
    def check_default_value_single_valued(self) -> "Property":
        if not self.default:
            return self

        if self.max_count is None or self.max_count > 1 or (self.min_count and self.min_count > 1):
            raise ValueError(
                "Setting default value is only supported for single-valued properties."
                f" Property has min_count={self.min_count} and max_count={self.max_count}."
            )
        return self

    @model_validator(mode="after")
    def check_default_value_type_match(self) -> "Property":
        if not self.default:
            return self

        if isinstance(self.value_type, DataType) and not isinstance(self.default, self.value_type.python):
            raise ValueError(
                f"Default value type is {type(self.default)}, which "
                f"does not match expected value type {self.value_type.python}."
            )
        return self
