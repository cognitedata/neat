"""Exports rules to CDF Data Model Storage.
"""

from typing import ClassVar, Optional, Self
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ContainerApply, ContainerProperty, DirectRelation
from cognite.client.data_classes.data_modeling import ViewApply, SpaceApply, DataModelApply, DirectRelationReference
from cognite.client.data_classes.data_modeling import MappedPropertyApply, ContainerId
from cognite.client.data_classes._base import CogniteResource
from cognite.neat.rules.analysis import to_class_property_pairs

from cognite.neat.rules.models import Property, TransformationRules, DATA_TYPE_MAPPING
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

    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, arbitrary_types_allowed=True, strict=False, extra="allow"
    )

    @classmethod
    def from_rules(cls, transformation_rules: TransformationRules, fix_names: bool = False) -> Self:
        names_compliant, name_warnings = are_entity_names_dms_compliant(transformation_rules, return_report=True)
        if not names_compliant:
            raise _exceptions.Error10(report=generate_exception_report(name_warnings))

        properties_redefined, redefinition_warnings = are_properties_redefined(transformation_rules, return_report=True)
        if properties_redefined:
            raise _exceptions.Error11(report=generate_exception_report(redefinition_warnings))

        return cls(
            space=transformation_rules.metadata.cdf_space_name,
            external_id=transformation_rules.metadata.data_model_name,  # type: ignore
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
                properties=DataModel.properties_from_dict(properties, transformation_rules.metadata.cdf_space_name),
            )
            for class_id, properties in class_properties.items()
        ]  # type: ignore

    @staticmethod
    def properties_from_dict(properties: dict[str, Property], space: str) -> dict[str, ContainerProperty]:
        container_properties = {}
        for property_id, property_definition in properties.items():
            type_ = (
                DATA_TYPE_MAPPING[property_definition.expected_value_type]["dms"]
                if property_definition.property_type == "DatatypeProperty"
                else DirectRelation(
                    container=ContainerId(space=space, external_id=property_definition.expected_value_type)
                )
            )

            container_properties[property_id] = ContainerProperty(
                type=type_(is_list=property_definition.max_count != 1)
                if property_definition.property_type == "DatatypeProperty"
                else type_,  # missing listable relations!
                nullable=property_definition.min_count == 0
                if property_definition.property_type == "DatatypeProperty"
                else True,
                default_value=property_definition.default,
                name=property_definition.property_name,
                description=property_definition.description,
            )

        return container_properties

    def to_cdf(self, client: CogniteClient):
        self.create_space(client)
        self.create_containers(client)
        self.create_data_model(client)

    def create_space(self, client: CogniteClient):
        if not client.data_modeling.spaces.retrieve(space=self.space):
            print(f"Creating space {self.space}")
            res = client.data_modeling.spaces.apply(SpaceApply(space=self.space))
        else:
            print(f"Space {self.space} already exists")

    def create_containers(self, client: CogniteClient):
        for container in self.containers:
            if not client.data_modeling.containers.retrieve((self.space, container.external_id)):
                print(f"Creating container {container.external_id} in space {self.space}")
                res = client.data_modeling.containers.apply(container)
            else:
                ...
                # raise warning that container already exists and it might cause problems
                # if there are changes in the model
                print(f"Container {container.external_id} already exists in space {self.space}")
                res = client.data_modeling.containers.apply(container)

    @property
    def views(self):
        return [self.generate_view(container) for container in self.containers]

    def generate_view(self, container: ContainerApply):
        mapped_properties = {
            external_id: MappedPropertyApply(
                container=ContainerId(space=self.space, external_id=container.external_id),
                container_property_identifier=external_id,
                name=definition.name,
                description=definition.description,
            )
            for external_id, definition in container.properties.items()
        }
        return ViewApply(
            space=self.space,
            external_id=container.external_id,
            name=container.name,
            version=self.version,
            properties=mapped_properties,
        )

    def create_data_model(self, client: CogniteClient):
        if not client.data_modeling.data_models.retrieve((self.space, self.external_id, self.version)):
            print(f"Creating data model {self.external_id} in space {self.space}")
            res = client.data_modeling.data_models.apply(
                DataModelApply(
                    name=self.name,
                    description=self.description,
                    space=self.space,
                    external_id=self.external_id,
                    version=self.version,
                    views=self.views,
                )
            )
        else:
            print(f"Data model {self.external_id} already exists in space {self.space}")
            # raise warning that model already exists and it might cause problems
            # if there are changes in the model
            res = client.data_modeling.data_models.apply(
                DataModelApply(
                    name=self.name,
                    description=self.description,
                    space=self.space,
                    external_id=self.external_id,
                    version=self.version,
                    views=self.views,
                )
            )
