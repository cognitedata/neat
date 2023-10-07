"""Exports rules to CDF Data Model Storage (DMS) through cognite-sdk.
"""

import logging
import sys
import warnings
from typing import ClassVar, cast

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import (
    ContainerApply,
    ContainerId,
    ContainerProperty,
    DataModelApply,
    DataModelId,
    DirectRelation,
    DirectRelationReference,
    MappedPropertyApply,
    SpaceApply,
    ViewApply,
    ViewId,
)
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType
from cognite.client.data_classes.data_modeling.views import (
    ConnectionDefinitionApply,
    SingleHopConnectionDefinitionApply,
)
from pydantic import BaseModel, ConfigDict

from cognite.neat.rules import exceptions
from cognite.neat.rules._validation import (
    are_entity_names_dms_compliant,
    are_properties_redefined,
)
from cognite.neat.rules.analysis import to_class_property_pairs
from cognite.neat.rules.models import DATA_TYPE_MAPPING, Property, TransformationRules
from cognite.neat.utils.utils import generate_exception_report


class DataModel(BaseModel):
    """
    Data model pydantic class used to create space, containers, views and data model in CDF.

    This can be used to create a data model in CDF from transformation rules.

    Args:
        space: Name of the space to place the resulting data model.
        external_id: External id of the data model.
        version: Version of the data model.
        description: Description of the data model.
        name: Name of the data model.
        containers: Containers connected to the data model.
        views: Views connected to the data model.

    """

    space: str
    external_id: str
    version: str
    description: str | None = None
    name: str | None = None
    containers: dict[str, ContainerApply]
    views: dict[str, ViewApply]

    model_config: ClassVar[ConfigDict] = ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, arbitrary_types_allowed=True, strict=False, extra="allow"
    )

    @classmethod
    def from_rules(cls, transformation_rules: TransformationRules) -> Self:
        """Generates a DataModel class instance from a TransformationRules instance.

        Args:
            transformation_rules: instance of TransformationRules.

        Returns:
            Instance of DataModel.
        """
        names_compliant, name_warnings = are_entity_names_dms_compliant(transformation_rules, return_report=True)
        if not names_compliant:
            logging.error(
                exceptions.EntitiesContainNonDMSCompliantCharacters(
                    report=generate_exception_report(name_warnings)
                ).message
            )
            raise exceptions.EntitiesContainNonDMSCompliantCharacters(report=generate_exception_report(name_warnings))

        properties_redefined, redefinition_warnings = are_properties_redefined(transformation_rules, return_report=True)
        if properties_redefined:
            logging.error(
                exceptions.PropertiesDefinedMultipleTimes(report=generate_exception_report(redefinition_warnings))
            )
            raise exceptions.PropertiesDefinedMultipleTimes(report=generate_exception_report(redefinition_warnings))

        if transformation_rules.metadata.data_model_name is None:
            logging.error(exceptions.DataModelNameMissing(prefix=transformation_rules.metadata.prefix).message)
            raise exceptions.DataModelNameMissing(prefix=transformation_rules.metadata.prefix)

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
            transformation_rules: instance of TransformationRules.`

        Returns:
            Dictionary of ContainerApply instances.
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
            properties: Dictionary of Property instances.

        Returns:
            Dictionary of ContainerProperty instances.
        """
        container_properties = {}
        for property_id, property_definition in properties.items():
            # Literal, i.e. attribute
            if property_definition.property_type == "DatatypeProperty":
                property_type = cast(
                    type[ListablePropertyType], DATA_TYPE_MAPPING[property_definition.expected_value_type]["dms"]
                )
                container_properties[property_id] = ContainerProperty(
                    type=property_type(is_list=property_definition.max_count != 1),
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
                logging.warning(
                    exceptions.ContainerPropertyTypeUnsupported(property_id, property_definition.property_type).message
                )
                warnings.warn(
                    exceptions.ContainerPropertyTypeUnsupported(property_id, property_definition.property_type).message,
                    category=exceptions.ContainerPropertyTypeUnsupported,
                    stacklevel=2,
                )

        return container_properties

    @staticmethod
    def views_from_rules(transformation_rules: TransformationRules) -> dict[str, ViewApply]:
        """Generates a dictionary of ViewApply instances from a TransformationRules instance.

        Args:
            transformation_rules: Iinstance of TransformationRules.

        Returns:
            Dictionary of ViewApply instances.
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
    ) -> dict[str, MappedPropertyApply | ConnectionDefinitionApply]:
        view_properties: dict[str, MappedPropertyApply | ConnectionDefinitionApply] = {}
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
                view_properties[property_id] = SingleHopConnectionDefinitionApply(
                    type=DirectRelationReference(
                        space=space, external_id=f"{property_definition.class_id}.{property_definition.property_id}"
                    ),
                    source=ViewId(space=space, external_id=property_definition.expected_value_type, version=version),
                    direction="outwards",
                    name=property_definition.property_name,
                    description=property_definition.description,
                )
            else:
                logging.warning(exceptions.ViewPropertyTypeUnsupported(property_id).message)
                warnings.warn(
                    exceptions.ViewPropertyTypeUnsupported(property_id).message,
                    category=exceptions.ViewPropertyTypeUnsupported,
                    stacklevel=2,
                )

        return view_properties

    def to_cdf(self, client: CogniteClient):
        """Write the the data model to CDF.

        Args:
            client: Connected Cognite client.

        """
        existing_data_model = self.find_existing_data_model(client)
        existing_containers = self.find_existing_containers(client)
        existing_views = self.find_existing_views(client)

        if existing_data_model or existing_containers or existing_views:
            raise exceptions.DataModelOrItsComponentsAlreadyExist(
                existing_data_model, existing_containers, existing_views
            )

        self.create_space(client)
        self.create_containers(client)
        self.create_views(client)
        self.create_data_model(client)

    def find_existing_data_model(self, client: CogniteClient) -> DataModelId | None:
        """Checks if the data model exists in CDF.

        Args:
            client: Cognite client.

        Returns:
             True if the data model exists, False otherwise.
        """
        if model := client.data_modeling.data_models.retrieve((self.space, self.external_id, self.version)):
            cdf_data_model = model.latest_version()
            logging.warning(exceptions.DataModelAlreadyExist(self.external_id, self.version, self.space).message)
            warnings.warn(
                exceptions.DataModelAlreadyExist(self.external_id, self.version, self.space).message,
                category=exceptions.DataModelAlreadyExist,
                stacklevel=2,
            )

            return cdf_data_model.as_id()
        return None

    def find_existing_containers(self, client: CogniteClient) -> set[ContainerId]:
        """Checks if the containers exist in CDF.

        Args:
            client: Cognite client.

        Returns:
            True if the containers exist, False otherwise.
        """

        cdf_containers = {}
        if containers := client.data_modeling.containers.list(space=self.space, limit=-1):
            cdf_containers = {container.as_id(): container for container in containers}

        if existing_containers := {c.as_id() for c in self.containers.values()}.intersection(
            set(cdf_containers.keys())
        ):
            logging.warning(exceptions.ContainersAlreadyExist(existing_containers, self.space).message)
            warnings.warn(
                exceptions.ContainersAlreadyExist(existing_containers, self.space).message,
                category=exceptions.ContainersAlreadyExist,
                stacklevel=2,
            )

            return existing_containers
        else:
            return set()

    def find_existing_views(self, client: CogniteClient) -> set[ViewId]:
        """Checks if the views exist in CDF.

        Args:
            client: Cognite client.

        Returns:
            True if the views exist, False otherwise.
        """
        cdf_views = {}
        if views := client.data_modeling.views.list(space=self.space, limit=-1):
            cdf_views = {view.as_id(): view for view in views if view.version == self.version}

        if existing_views := {v.as_id() for v in self.views.values()}.intersection(set(cdf_views.keys())):
            logging.warning(exceptions.ViewsAlreadyExist(existing_views, self.version, self.space).message)
            warnings.warn(
                exceptions.ViewsAlreadyExist(existing_views, self.version, self.space).message,
                category=exceptions.ViewsAlreadyExist,
                stacklevel=2,
            )
            return existing_views
        else:
            return set()

    def create_space(self, client: CogniteClient):
        logging.info(f"Creating space {self.space}")
        _ = client.data_modeling.spaces.apply(SpaceApply(space=self.space))

    def create_containers(self, client: CogniteClient):
        for container_id in self.containers:
            logging.info(f"Creating container {container_id} in space {self.space}")
            _ = client.data_modeling.containers.apply(self.containers[container_id])

    def create_views(self, client: CogniteClient):
        for view_id in self.views:
            logging.info(f"Creating view {view_id} version {self.views[view_id].version} in space {self.space}")
            _ = client.data_modeling.views.apply(self.views[view_id])

    def create_data_model(self, client: CogniteClient):
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
            client: Cognite client.
        """

        if client.data_modeling.data_models.retrieve((self.space, self.external_id, self.version)):
            logging.info(f"Removing data model {self.external_id} version {self.version} from space {self.space}")
            _ = client.data_modeling.data_models.delete((self.space, self.external_id, self.version))

        if views := client.data_modeling.views.retrieve(
            [view.as_id() for view in self.views.values()], all_versions=False
        ):
            for view in views:
                logging.info(f"Removing view {view.external_id} version {view.version} from space {self.space}")
                _ = client.data_modeling.views.delete((view.space, view.external_id, view.version))

        if containers := client.data_modeling.containers.retrieve(
            [container.as_id() for container in self.containers.values()]
        ):
            for container in containers:
                logging.info(f"Removing container {container.external_id} from space {self.space}")
                _ = client.data_modeling.containers.delete((container.space, container.external_id))
