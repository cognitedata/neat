"""Exports rules to CDF Data Model Storage (DMS) through cognite-sdk.
"""

import logging
from typing import ClassVar, Optional, Self
import warnings
from pydantic import BaseModel, ConfigDict

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import ContainerApply, ContainerProperty, DirectRelation
from cognite.client.data_classes.data_modeling import (
    ViewApply,
    SpaceApply,
    DataModelApply,
    DirectRelationReference,
)
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
    """Data model pydantic class used to create space, containers, views and data model in CDF.
    based on the transformation rules."""

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
        """Generates a DataModel class instance from a TransformationRules instance.

        Args:
            transformation_rules (TransformationRules): instance of TransformationRules.
            fix_names (bool, optional): Flag to fix non-compliant names. Defaults to False.

        Returns:
            DataModel: instance of DataModel.
        """
        names_compliant, name_warnings = are_entity_names_dms_compliant(transformation_rules, return_report=True)
        if not names_compliant:
            logging.error(_exceptions.Error10(report=generate_exception_report(name_warnings)).message)
            raise _exceptions.Error10(report=generate_exception_report(name_warnings))

        properties_redefined, redefinition_warnings = are_properties_redefined(transformation_rules, return_report=True)
        if properties_redefined:
            logging.error(_exceptions.Error11(report=generate_exception_report(redefinition_warnings)))
            raise _exceptions.Error11(report=generate_exception_report(redefinition_warnings))

        return cls(
            space=transformation_rules.metadata.cdf_space_name,
            external_id=transformation_rules.metadata.data_model_name,
            version=transformation_rules.metadata.version,
            description=transformation_rules.metadata.description,
            name=transformation_rules.metadata.title,
            containers=cls.containers_from_rules(transformation_rules),
            views=cls.views_from_rules(transformation_rules),
        )

    @staticmethod
    def containers_from_rules(transformation_rules: TransformationRules) -> dict[str, ContainerApply]:
        """Create a dictionary of ContainerApply instances from a TransformationRules instance.

        Args:
            transformation_rules (TransformationRules): instance of TransformationRules.`

        Returns:
            dict[str, ContainerApply]: dictionary of ContainerApply instances.
        """
        class_properties = to_class_property_pairs(transformation_rules)
        return {
            class_id: ContainerApply(
                space=transformation_rules.metadata.cdf_space_name,
                external_id=class_id,
                name=transformation_rules.classes[class_id].class_name,
                description=transformation_rules.classes[class_id].description,
                properties=DataModel.container_properties_from_dict(properties),
            )
            for class_id, properties in class_properties.items()
        }

    @staticmethod
    def container_properties_from_dict(properties: dict[str, Property]) -> dict[str, ContainerProperty]:
        """Generates a dictionary of ContainerProperty instances from a dictionary of Property instances.

        Args:
            properties (dict[str, Property]): dictionary of Property instances.

        Returns:
            dict[str, ContainerProperty]: dictionary of ContainerProperty instances.
        """
        container_properties = {}
        for property_id, property_definition in properties.items():
            # Literal, i.e. attribute
            if property_definition.property_type == "DatatypeProperty":
                container_properties[property_id] = ContainerProperty(
                    type=DATA_TYPE_MAPPING[property_definition.expected_value_type]["dms"](
                        is_list=property_definition.max_count != 1
                    ),
                    nullable=property_definition.min_count == 0,
                    default_value=property_definition.default,
                    name=property_definition.property_name,
                    description=property_definition.description,
                )

            # URIRef, i.e. edge
            elif property_definition.property_type == "ObjectProperty":
                container_properties[property_id] = ContainerProperty(
                    type=DirectRelation(),
                    nullable=True,
                    name=property_definition.property_name,
                    description=property_definition.description,
                )
            else:
                logging.warning(_exceptions.Warning60(property_id, property_definition.property_type).message)
                warnings.warn(
                    _exceptions.Warning60(property_id, property_definition.property_type).message,
                    category=_exceptions.Warning60,
                    stacklevel=2,
                )

        return container_properties

    @staticmethod
    def views_from_rules(transformation_rules: TransformationRules) -> dict[str, ViewApply]:
        """Generates a dictionary of ViewApply instances from a TransformationRules instance.

        Args:
            transformation_rules (TransformationRules): instance of TransformationRules.

        Returns:
            dict[str, ViewApply]: dictionary of ViewApply instances.
        """
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
        }

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
                logging.warning(_exceptions.Warning61(property_id).message)
                warnings.warn(
                    _exceptions.Warning61(property_id).message,
                    category=_exceptions.Warning61,
                    stacklevel=2,
                )

        return view_properties

    def to_cdf(self, client: CogniteClient):
        """Creates the data model in CDF.

        Args:
            client (CogniteClient): Cognite client.
        """
        self.create_space(client)
        self.create_containers(client)
        self.create_views(client)
        self.create_data_model(client)

    def create_space(self, client: CogniteClient):
        if not client.data_modeling.spaces.retrieve(space=self.space):
            logging.info(f"Creating space {self.space}")
            _ = client.data_modeling.spaces.apply(SpaceApply(space=self.space))
        else:
            logging.info(f"Space {self.space} already exists. Skipping creation!")

    def create_containers(self, client: CogniteClient):
        cdf_containers = {}
        if containers := client.data_modeling.containers.list(space=self.space, limit=-1):
            cdf_containers = {container.external_id: container for container in containers}

        if existing_containers := set(self.containers.keys()).intersection(set(cdf_containers.keys())):
            logging.warning(_exceptions.Warning62(existing_containers, self.space).message)
            warnings.warn(
                _exceptions.Warning62(existing_containers, self.space).message,
                category=_exceptions.Warning62,
                stacklevel=2,
            )
        else:
            for container_id in self.containers:
                logging.info(f"Creating container {container_id} in space {self.space}")
                _ = client.data_modeling.containers.apply(self.containers[container_id])

    def create_views(self, client: CogniteClient, force: bool = False):
        cdf_views = {}
        if views := client.data_modeling.views.list(space=self.space, limit=-1):
            cdf_views = {container.external_id: container for container in views}

        if existing_views := set(self.views.keys()).intersection(set(cdf_views.keys())):
            logging.warning(_exceptions.Warning63(existing_views, self.version, self.space).message)
            warnings.warn(
                _exceptions.Warning63(existing_views, self.version, self.space).message,
                category=_exceptions.Warning63,
                stacklevel=2,
            )
        else:
            for view_id in self.views:
                logging.info(f"Creating view {view_id} version {self.views[view_id].version} in space {self.space}")
                _ = client.data_modeling.views.apply(self.views[view_id])

    def create_data_model(self, client: CogniteClient):
        cdf_data_model = {}

        if model := client.data_modeling.data_models.retrieve((self.space, self.external_id, self.version)):
            cdf_data_model = model[0]

        if cdf_data_model:
            logging.warning(_exceptions.Warning64(self.external_id, self.version, self.space).message)
            warnings.warn(
                _exceptions.Warning64(self.external_id, self.version, self.space).message,
                category=_exceptions.Warning64,
                stacklevel=2,
            )
        else:
            logging.info(f"Creating data model {self.external_id} version {self.version} in space {self.space}")
            _ = client.data_modeling.data_models.apply(
                DataModelApply(
                    name=self.name,
                    description=self.description,
                    space=self.space,
                    external_id=self.external_id,
                    version=self.version,
                    views=list(self.views.values()),
                )
            )

    def remove_data_model(self, client: CogniteClient):
        """Helper function to remove a data model, and all underlying views and containers from CDF.

        Args:
            client (CogniteClient): Cognite client.
        """

        if client.data_modeling.data_models.retrieve((self.space, self.external_id, self.version)):
            logging.info(f"Removing data model {self.external_id} version {self.version} from space {self.space}")
            _ = client.data_modeling.data_models.delete((self.space, self.external_id, self.version))

        if views := client.data_modeling.views.retrieve([view.as_id() for view in self.views.values()]):
            for view in views:
                logging.info(f"Removing view {view.external_id} version {view.version} from space {self.space}")
                _ = client.data_modeling.views.delete((view.space, view.external_id, view.version))

        if containers := client.data_modeling.containers.retrieve(
            [container.as_id() for container in self.containers.values()]
        ):
            for container in containers:
                logging.info(f"Removing container {container.external_id} from space {self.space}")
                _ = client.data_modeling.containers.delete((container.space, container.external_id))
