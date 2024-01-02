"""Exports rules to CDF Data Model Storage (DMS) through cognite-sdk.
"""

import dataclasses
import logging
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal, cast

import yaml

from cognite.neat.rules.value_types import ValueTypeMapping

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import (
    ContainerApply,
    ContainerApplyList,
    ContainerId,
    ContainerProperty,
    DataModelApply,
    DataModelId,
    DirectRelation,
    DirectRelationReference,
    MappedPropertyApply,
    PropertyType,
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
from cognite.neat.rules.exporter._base import BaseExporter
from cognite.neat.rules.exporter._validation import are_entity_names_dms_compliant
from cognite.neat.rules.models._base import ContainerEntity, EntityTypes, ParentClass
from cognite.neat.rules.models.rules import Property, Rules
from cognite.neat.utils.utils import generate_exception_report

if sys.version_info < (3, 11):
    from exceptiongroup import ExceptionGroup


@dataclass
class EmptyPropertyType(PropertyType):
    _type = "No property"


@dataclass
class DMSSchema:
    data_model: DataModelApply
    containers: ContainerApplyList


class DMSExporter(BaseExporter[DMSSchema]):
    """Class for exporting transformation rules object to CDF Data Model Storage (DMS).

    Args:
        rules: Transformation rules object.
        data_model_id: The id of the data model to be created.
        container_policy: How to create/reuse existing containers.
        existing_model: In the case of updating an existing model, this is the existing model.
        report: Report. This is used when the exporter object is created from RawRules

    !!! note "Container policy"
        Here is more information about the different container policies:
        - `create`: assumes no containers exist in CDF, will attempt to create them
        - `reuse`: assumes containers exists in CDF, will attempt to only re-use them
        - `extend`: will re-use existing, extend and/or create only missing containers
        - `optimize`: create containers of size's prescribed by NEAT's optimization algorithm
    """

    def __init__(
        self,
        rules: Rules,
        data_model_id: dm.DataModelId | None = None,
        container_policy: Literal["create", "reuse", "extend", "optimize"] = "create",
        existing_model: dm.DataModel[dm.View] | None = None,
        report: str | None = None,
    ):
        super().__init__(rules, report)
        self.data_model_id = data_model_id
        self.container_policy = container_policy
        if container_policy == "extend" and existing_model is None:
            raise ValueError("Container policy is extend-existing, but no existing model is provided")
        if container_policy != "create":
            raise NotImplementedError("Only one-to-one-view container policy is currently supported")
        self.existing_model = existing_model

    def _export_to_file(self, filepath: Path) -> None:
        if filepath.suffix not in {".yaml", ".yml"}:
            warnings.warn("File extension is not .yaml, adding it to the file name", stacklevel=2)
            filepath = filepath.with_suffix(".yaml")
        schema = self.export()
        filepath.write_text(
            yaml.safe_dump(
                {
                    "data_models": [schema.data_model.dump(camel_case=True)],
                    "containers": schema.containers.dump(camel_case=True),
                }
            )
        )

    def export(self) -> DMSSchema:
        model = DataModel.from_rules(self.rules, self.data_model_id)
        return DMSSchema(
            data_model=DataModelApply(
                space=model.space,
                external_id=model.external_id,
                version=model.version,
                description=model.description,
                name=model.name,
                views=list(model.views.values()),
            ),
            containers=ContainerApplyList(model.containers.values()),
        )


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

    @property
    def spaces(self):
        return set(
            [container.space for container in self.containers.values()]
            + [self.space]
            + [view.space for view in self.views.values()]
        )

    @classmethod
    def from_rules(
        cls, rules: Rules, data_model_id: dm.DataModelId | None = None, set_expected_source: bool = True
    ) -> Self:
        """Generates a DataModel class instance from a Rules instance.

        Args:
            rules: instance of Rules.
            data_model_id: The id of the data model to be created.
            set_expected_source: Whether to set the expected source on views with direct relation properties.

        Returns:
            Instance of DataModel.
        """
        if data_model_id and data_model_id.space:
            # update space in rules to match space
            rules.update_space(data_model_id.space)

        if data_model_id and data_model_id.version:
            # update version in rules to match version
            rules.update_version(data_model_id.version)

        if data_model_id and data_model_id.external_id:
            # update data model name to match external_id
            rules.metadata.suffix = data_model_id.external_id

        names_compliant, name_warnings = are_entity_names_dms_compliant(rules, return_report=True)
        if not names_compliant:
            raise exceptions.EntitiesContainNonDMSCompliantCharacters(report=generate_exception_report(name_warnings))

        if rules.metadata.external_id is None:
            raise exceptions.DataModelIdMissing(prefix=rules.metadata.space)

        return cls(
            space=rules.metadata.space,
            external_id=rules.metadata.external_id,
            version=rules.metadata.version,
            description=rules.metadata.description,
            name=rules.metadata.name,
            containers=cls.containers_from_rules(rules),
            views=cls.views_from_rules(rules),
        )

    @staticmethod
    def containers_from_rules(rules: Rules) -> dict[str, ContainerApply]:
        """Create a dictionary of ContainerApply instances from a Rules instance.

        Args:
            rules: instance of Rules.`

        Returns:
            Dictionary of ContainerApply instances.
        """

        containers: dict[str, ContainerApply] = {}
        errors: list = []

        for row, property_ in rules.properties.items():
            if property_.container:
                container_property_id: str = cast(str, property_.container_property)
                container_id = property_.container.id

                api_container = DataModel.as_api_container(property_.container)
                api_container_property = DataModel.as_api_container_property(property_)

                # scenario: adding new container to the data model for the first time
                if not isinstance(api_container_property.type, EmptyPropertyType) and container_id not in containers:
                    containers[container_id] = api_container
                    containers[container_id].properties[container_property_id] = api_container_property

                # scenario: adding new property to an existing container
                elif (
                    not isinstance(api_container_property.type, EmptyPropertyType)
                    and container_property_id not in containers[container_id].properties
                ):
                    containers[container_id].properties[container_property_id] = api_container_property

                # scenario: property is redefined checking for potential sub-scenarios
                elif (
                    not isinstance(api_container_property.type, EmptyPropertyType)
                    and container_property_id in containers[container_id].properties
                ):
                    existing_property = containers[container_id].properties[container_property_id]

                    # scenario: property is redefined with a different value type -> raise error
                    if not isinstance(existing_property.type, type(api_container_property.type)):
                        errors.append(
                            exceptions.ContainerPropertyValueTypeRedefinition(
                                container_id=container_id,
                                property_id=container_property_id,
                                current_value_type=str(existing_property.type),
                                redefined_value_type=str(api_container_property.type),
                                loc=f"[Properties/Type/{row}]",
                            )
                        )

                    # scenario: default value is redefined -> set default value to None
                    if (
                        not isinstance(existing_property.type, DirectRelation)
                        and not isinstance(api_container_property.type, DirectRelation)
                        and existing_property.default_value != api_container_property.default_value
                    ):
                        containers[container_id].properties[container_property_id] = dataclasses.replace(
                            existing_property, default_value=None
                        )

                    # scenario: property hold multiple values -> set is_list to True
                    if (
                        not isinstance(existing_property.type, DirectRelation)
                        and not isinstance(api_container_property.type, DirectRelation)
                        and cast(ListablePropertyType, existing_property.type).is_list
                        != cast(ListablePropertyType, api_container_property.type).is_list
                    ):
                        cast(
                            ListablePropertyType, containers[container_id].properties[container_property_id].type
                        ).is_list = True

        if errors:
            raise ExceptionGroup("Properties value types have been redefined! This is prohibited! Aborting!", errors)

        return containers

    @staticmethod
    def as_api_container_property(property_: Property) -> ContainerProperty:
        is_one_to_many = property_.max_count != 1

        # Literal, i.e. Node attribute
        if property_.property_type is EntityTypes.data_property:
            property_type = cast(
                type[ListablePropertyType],
                cast(ValueTypeMapping, property_.expected_value_type.mapping).dms,
            )
            return ContainerProperty(
                type=property_type(is_list=is_one_to_many),
                nullable=property_.min_count == 0,
                default_value=property_.default,
                name=property_.property_name,
                description=property_.description,
            )

        # URIRef, i.e. edge 1-1 , aka direct relation between Nodes
        elif property_.property_type is EntityTypes.object_property and not is_one_to_many:
            return ContainerProperty(
                type=DirectRelation(),
                nullable=True,
                name=property_.property_name,
                description=property_.description,
            )

        # return type=None if property cannot be created
        else:
            return ContainerProperty(type=EmptyPropertyType())

    @staticmethod
    def as_api_container(container: ContainerEntity) -> ContainerApply:
        return ContainerApply(
            space=container.space,
            external_id=container.external_id,
            description=container.description,
            name=container.name,
            # properties are added later
            properties={},
        )

    @staticmethod
    def views_from_rules(rules: Rules) -> dict[str, ViewApply]:
        """Generates a dictionary of ViewApply instances from a Rules instance.

        Args:
            rule: Instance of Rules.
            space: Name of the space to place the views.

        Returns:
            Dictionary of ViewApply instances.
        """
        views: dict[str, ViewApply] = {}
        errors: list = []

        # Create views from property-class definitions
        for row, property_ in rules.properties.items():
            view_property = DataModel.view_property_from_rules_property(property_, rules.metadata.space)
            id_ = f"{rules.metadata.space}:{property_.class_id}"

            # scenario: view does not exist
            if view_property and id_ not in views:
                views[id_] = ViewApply(
                    space=rules.metadata.space,
                    external_id=property_.class_id,
                    version=rules.metadata.version,
                    name=rules.classes[property_.class_id].class_name if property_.class_id in rules.classes else None,
                    description=rules.classes[property_.class_id].description
                    if property_.class_id in rules.classes
                    else None,
                    properties={property_.property_id: view_property},
                    implements=[
                        parent_class.view_id
                        for parent_class in cast(list[ParentClass], rules.classes[property_.class_id].parent_class)
                    ]
                    if (property_.class_id in rules.classes and rules.classes[property_.class_id].parent_class)
                    else None,
                )

            # scenario: view exist but property does not so it is added
            elif view_property and (
                property_.property_id
                not in cast(dict[str, MappedPropertyApply | ConnectionDefinitionApply], views[id_].properties)
            ):
                cast(dict[str, MappedPropertyApply | ConnectionDefinitionApply], views[id_].properties)[
                    property_.property_id
                ] = view_property

            # scenario: view exist, property exists but it is differently defined -> raise error
            elif (
                view_property
                and property_.property_id
                in cast(dict[str, MappedPropertyApply | ConnectionDefinitionApply], views[id_].properties)
                and view_property
                is not cast(dict[str, MappedPropertyApply | ConnectionDefinitionApply], views[id_].properties)[
                    property_.property_id
                ]
            ):
                errors.append(
                    exceptions.ViewPropertyRedefinition(
                        view_id=id_,
                        property_id=cast(str, property_.container_property),
                        loc=f"[Properties/Property/{row}]",
                    )
                )

        if errors:
            raise ExceptionGroup("View properties have been redefined! This is prohibited! Aborting!", errors)

        return views

    @staticmethod
    def view_property_from_rules_property(
        property_: Property, space: str
    ) -> MappedPropertyApply | ConnectionDefinitionApply | None:
        property_.container = cast(ContainerEntity, property_.container)
        property_.container_property = cast(str, property_.container_property)
        if property_.property_type is EntityTypes.data_property:
            return MappedPropertyApply(
                container=ContainerId(space=property_.container.space, external_id=property_.container.external_id),
                container_property_identifier=property_.container_property,
                name=property_.property_name,
                description=property_.description,
            )

        # edge 1-1 == directRelation
        elif property_.property_type is EntityTypes.object_property and property_.max_count == 1:
            return MappedPropertyApply(
                container=ContainerId(space=property_.container.space, external_id=property_.container.external_id),
                container_property_identifier=property_.container_property,
                name=property_.property_name,
                description=property_.description,
                source=ViewId(
                    space=property_.expected_value_type.space,
                    external_id=property_.expected_value_type.external_id,
                    version=property_.expected_value_type.version,
                ),
            )

        # edge 1-many == EDGE, this does not have container! type is here source ViewId ?!
        elif property_.property_type is EntityTypes.object_property and property_.max_count != 1:
            return SingleHopConnectionDefinitionApply(
                type=DirectRelationReference(space=space, external_id=f"{property_.class_id}.{property_.property_id}"),
                # Here we create ViewID to the container that the edge is pointing to.
                source=ViewId(
                    space=property_.expected_value_type.space,
                    external_id=property_.expected_value_type.external_id,
                    version=property_.expected_value_type.version,
                ),
                direction="outwards",
                name=property_.property_name,
                description=property_.description,
            )
        else:
            return None

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

    def find_existing_containers(self, client: CogniteClient) -> set:
        """Checks if the containers exist in CDF.

        Args:
            client: Cognite client.

        Returns:
            True if the containers exist, False otherwise.
        """

        existing_containers = set()

        for id_, container in self.containers.items():
            if client.data_modeling.containers.retrieve(container.as_id()):
                existing_containers.add(id_)

        return existing_containers

    def find_existing_views(self, client: CogniteClient) -> set:
        """Checks if the views exist in CDF.

        Args:
            client: Cognite client.

        Returns:
            True if the views exist, False otherwise.
        """

        existing_views = set()

        for id_, view in self.views.items():
            if client.data_modeling.views.retrieve(view.as_id()):
                existing_views.add(id_)

        return existing_views

    def create_space(self, client: CogniteClient):
        logging.info(f"Creating space {self.space}")

        for space in self.spaces:
            _ = client.data_modeling.spaces.apply(SpaceApply(space=space))

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
