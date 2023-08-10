"""Exports rules to CDF Data Model Storage.
"""

from typing import Optional, Self
from pydantic import BaseModel, Field, model_validator, field_validator

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ContainerApply, ContainerProperty, Text
from cognite.client.data_classes._base import CogniteResource
from cognite.neat.rules.analysis import to_class_property_pairs

from cognite.neat.rules.models import Property, TransformationRules
from cognite.neat.rules import _exceptions
from cognite.neat.rules._validation import (
    are_entity_names_dms_compliant,
    are_properties_redefined,
)
from cognite.neat.utils.utils import generate_exception_report


class DataModel(BaseModel):
    space: str
    external_id: str
    version: str
    description: Optional[str] = None
    name: Optional[str] = None
    containers: list[ContainerApply]

    @classmethod
    def from_rules(cls, transformation_rules: TransformationRules) -> Self:
        names_compliant, name_warnings = are_entity_names_dms_compliant(transformation_rules, return_report=True)
        if not names_compliant:
            raise _exceptions.Error10(report=generate_exception_report(name_warnings))

        properties_redefined, redefinition_warnings = are_properties_redefined(transformation_rules, return_report=True)
        if properties_redefined:
            raise _exceptions.Error11(report=generate_exception_report(redefinition_warnings))

        return cls(
            space=transformation_rules.metadata.cdf_space_name,
            external_id=transformation_rules.metadata.data_model_name,
            version=transformation_rules.metadata.version,
            description=transformation_rules.metadata.description,
            name=transformation_rules.metadata.title,
            containers=cls.containers_from_rules(transformation_rules),
        )

    @staticmethod
    def containers_from_rules(transformation_rules: TransformationRules) -> list[ContainerApply]:
        class_properties = to_class_property_pairs(transformation_rules)
        return [
            ContainerApply(
                space=transformation_rules.metadata.cdf_space_name,
                external_id=class_id,
                name=transformation_rules.classes[class_id].class_name,
                properties=DataModel.properties_from_dict(properties),
            )
            for class_id, properties in class_properties.items()
        ]

    @staticmethod
    def properties_from_dict(properties: dict[str, Property]) -> dict[str, ContainerProperty]:
        for property_id, property_definition in properties.items():
            type = property_definition.expected_value_type

        ...

    def to_cdf(self, client: CogniteClient):
        # create space if it is missing
        # create data model if it is missing
        # create containers if they are missing
        # create properties if they are missing
        ...

    def create_space(self, client: CogniteClient):
        ...

    def create_data_model(self, client: CogniteClient):
        ...

    def create_containers(self, client: CogniteClient):
        ...
