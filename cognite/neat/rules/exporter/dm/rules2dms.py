"""Exports rules to CDF Data Model Storage (DMS) through cognite-sdk.
"""

from typing import ClassVar, Optional, Self
from pydantic import BaseModel, ConfigDict

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ContainerApply, ContainerProperty, DirectRelation
from cognite.client.data_classes.data_modeling import ViewApply, SpaceApply, DataModelApply, DirectRelationReference
from cognite.client.data_classes.data_modeling import (
    MappedPropertyApply,
    ContainerId,
    ViewId,
    SingleHopConnectionDefinition,
)
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
    containers: dict[str, ContainerApply]
    views: dict[str, ViewApply]

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
            views=cls.views_from_rules(transformation_rules),
        )

    @staticmethod
    def containers_from_rules(transformation_rules: TransformationRules) -> dict[str, ContainerApply]:
        class_properties = to_class_property_pairs(transformation_rules)
        return {
            class_id: ContainerApply(
                space=transformation_rules.metadata.cdf_space_name,
                external_id=class_id,
                name=transformation_rules.classes[class_id].class_name,
                description=transformation_rules.classes[class_id].description,
                properties=DataModel.container_properties_from_dict(
                    properties, transformation_rules.metadata.cdf_space_name
                ),
            )
            for class_id, properties in class_properties.items()
        }  # type: ignore

    @staticmethod
    def container_properties_from_dict(properties: dict[str, Property], space: str) -> dict[str, ContainerProperty]:
        container_properties = {}
        for property_id, property_definition in properties.items():
            if property_definition.property_type == "DatatypeProperty":  # Literal
                container_properties[property_id] = ContainerProperty(
                    type=DATA_TYPE_MAPPING[property_definition.expected_value_type]["dms"](
                        is_list=property_definition.max_count != 1
                    ),
                    nullable=property_definition.min_count == 0,
                    default_value=property_definition.default,
                    name=property_definition.property_name,
                    description=property_definition.description,
                )

            elif property_definition.property_type == "ObjectProperty":  # URIRef
                container_properties[property_id] = ContainerProperty(
                    type=DirectRelation(),
                    nullable=True,
                    name=property_definition.property_name,
                    description=property_definition.description,
                )

        return container_properties

    @staticmethod
    def views_from_rules(transformation_rules: TransformationRules) -> dict[str, ViewApply]:
        class_properties = to_class_property_pairs(transformation_rules)
        return {
            class_id: ViewApply(
                space=transformation_rules.metadata.cdf_space_name,
                external_id=class_id,
                name=transformation_rules.classes[class_id].class_name,
                description=transformation_rules.classes[class_id].description,
                properties=DataModel.view_properties_from_dict(
                    properties, transformation_rules.metadata.cdf_space_name, transformation_rules.metadata.version
                ),
                version=transformation_rules.metadata.version,
            )
            for class_id, properties in class_properties.items()
        }  # type: ignore

    @staticmethod
    def view_properties_from_dict(
        properties: dict[str, Property], space: str, version: str
    ) -> dict[str, MappedPropertyApply | SingleHopConnectionDefinition]:
        view_properties = {}
        for property_id, property_definition in properties.items():
            # attribute
            if property_definition.property_type == "DatatypeProperty":
                view_properties[property_id] = MappedPropertyApply(
                    container=ContainerId(space=space, external_id=property_definition.class_id),
                    container_property_identifier=property_id,
                    name=property_definition.property_name,
                    description=property_definition.description,
                )

            # edge 1-1
            elif property_definition.property_type == "ObjectProperty" and property_definition.max_count == 1:
                view_properties[property_id] = MappedPropertyApply(
                    container=ContainerId(space=space, external_id=property_definition.class_id),
                    container_property_identifier=property_id,
                    name=property_definition.property_name,
                    description=property_definition.description,
                    source=ViewId(space=space, external_id=property_definition.expected_value_type, version=version),
                )

            # edge 1-many
            elif property_definition.property_type == "ObjectProperty" and property_definition.max_count != 1:
                view_properties[property_id] = SingleHopConnectionDefinition(
                    type=DirectRelationReference(
                        space=space, external_id=f"{property_definition.class_id}.{property_definition.property_id}"
                    ),
                    source=ViewId(space=space, external_id=property_definition.expected_value_type, version=version),
                    direction="outwards",
                    name=property_definition.property_name,
                    description=property_definition.description,
                )
            else:
                ...
            # warning that the property type is not supported
            # logging

        return view_properties

    def to_cdf(self, client: CogniteClient):
        self.create_space(client)
        self.create_containers(client)
        self.create_views(client)
        self.create_data_model(client)

    def create_space(self, client: CogniteClient):
        if not client.data_modeling.spaces.retrieve(space=self.space):
            print(f"Creating space {self.space}")
            res = client.data_modeling.spaces.apply(SpaceApply(space=self.space))
        else:
            print(f"Space {self.space} already exists")

    def create_containers(self, client: CogniteClient):
        for container_id, container in self.containers.items():
            if not client.data_modeling.containers.retrieve((self.space, container_id)):
                print(f"Creating container {container_id} in space {self.space}")
                res = client.data_modeling.containers.apply(container)
            else:
                ...
                # raise warning that container already exists and it might cause problems
                # if there are changes in the model
                print(f"Container {container_id} already exists in space {self.space}")
                res = client.data_modeling.containers.apply(container)

    def create_views(self, client: CogniteClient):
        for view_id, view in self.views.items():
            if not client.data_modeling.views.retrieve((self.space, view_id, self.version)):
                print(f"Creating view {view_id} version {self.version} in space {self.space}")
                res = client.data_modeling.views.apply(view)
            else:
                ...
                # raise warning that container already exists and it might cause problems
                # if there are changes in the model
                print(f"View {view_id} version {self.version} exists in space {self.space}, attempting to update")
                res = client.data_modeling.views.apply(view)

    def create_data_model(self, client: CogniteClient):
        if not client.data_modeling.data_models.retrieve((self.space, self.external_id, self.version)):
            print(f"Creating data model {self.external_id} version {self.version} in space {self.space}")
            res = client.data_modeling.data_models.apply(
                DataModelApply(
                    name=self.name,
                    description=self.description,
                    space=self.space,
                    external_id=self.external_id,
                    version=self.version,
                    views=list(self.views.values()),
                )  # type: ignore
            )
        else:
            print(
                (
                    f"Data model {self.external_id} version {self.version} already exists"
                    f" in space {self.space}, attempting to update"
                )
            )
            # raise warning that model already exists and it might cause problems
            # if there are changes in the model
            res = client.data_modeling.data_models.apply(
                DataModelApply(
                    name=self.name,
                    description=self.description,
                    space=self.space,
                    external_id=self.external_id,
                    version=self.version,
                    views=list(self.views.values()),
                )  # type: ignore
            )
