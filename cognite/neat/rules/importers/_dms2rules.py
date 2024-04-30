from pathlib import Path
from typing import Literal, cast, overload

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import DataModelIdentifier
from cognite.client.data_classes.data_modeling.containers import BTreeIndex, InvertedIndex
from cognite.client.utils import ms_to_datetime

from cognite.neat.rules import issues
from cognite.neat.rules.importers._base import BaseImporter, Rules
from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    ViewEntity,
    ViewPropertyEntity,
)
from cognite.neat.rules.models.rules import DMSRules, DMSSchema, RoleTypes
from cognite.neat.rules.models.rules._base import ExtensionCategory, SchemaCompleteness
from cognite.neat.rules.models.rules._dms_architect_rules import (
    DMSContainer,
    DMSMetadata,
    DMSProperty,
    DMSView,
    SheetList,
)


class DMSImporter(BaseImporter):
    def __init__(self, schema: DMSSchema, metadata: DMSMetadata | None = None):
        self.schema = schema
        self.metadata = metadata

    @classmethod
    def from_data_model_id(cls, client: CogniteClient, data_model_id: DataModelIdentifier) -> "DMSImporter":
        """Create a DMSImporter ready to convert the given data model to rules.

        Args:
            client: Instantiated CogniteClient to retrieve data model.
            data_model_id: Data Model to retrieve.

        Returns:
            DMSImporter: DMSImporter instance
        """
        data_models = client.data_modeling.data_models.retrieve(data_model_id, inline_views=True)
        if len(data_models) == 0:
            raise ValueError(f"Data model {data_model_id} not found")
        data_model = data_models.latest_version()
        schema = DMSSchema.from_data_model(client, data_model)
        description, creator = DMSMetadata._get_description_and_creator(data_model.description)

        created = ms_to_datetime(data_model.created_time)
        updated = ms_to_datetime(data_model.last_updated_time)

        metadata = DMSMetadata(
            schema_=SchemaCompleteness.complete,
            extension=ExtensionCategory.addition,
            space=data_model.space,
            external_id=data_model.external_id,
            name=data_model.name or data_model.external_id,
            version=data_model.version or "0.1.0",
            updated=updated,
            created=created,
            creator=creator,
            description=description,
            default_view_version=data_model.version or "0.1.0",
        )
        return cls(schema, metadata)

    @classmethod
    def from_directory(cls, directory: str | Path) -> "DMSImporter":
        return cls(DMSSchema.from_directory(directory))

    @classmethod
    def from_zip_file(cls, zip_file: str | Path) -> "DMSImporter":
        if Path(zip_file).suffix != ".zip":
            raise ValueError("File extension is not .zip")
        return cls(DMSSchema.from_zip(zip_file))

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules:
        ...

    @overload
    def to_rules(
        self, errors: Literal["continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList]:
        ...

    def to_rules(
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
        if role is RoleTypes.domain_expert:
            raise ValueError(f"Role {role} is not supported for DMSImporter")
        issue_list = IssueList()
        data_model = self.schema.data_models[0]

        container_by_id = {container.as_id(): container for container in self.schema.containers}

        properties = SheetList[DMSProperty]()
        for view in self.schema.views:
            class_entity = ClassEntity(prefix=view.space, suffix=view.external_id, version=view.version)
            for prop_id, prop in (view.properties or {}).items():
                if isinstance(prop, dm.MappedPropertyApply):
                    if prop.container not in container_by_id:
                        raise ValueError(f"Container {prop.container} not found")
                    container = container_by_id[prop.container]
                    if prop.container_property_identifier not in container.properties:
                        raise ValueError(
                            f"Property {prop.container_property_identifier} not found "
                            f"in container {container.external_id}"
                        )
                    container_prop = container.properties[prop.container_property_identifier]

                    index: list[str] = []
                    for index_name, index_obj in (container.indexes or {}).items():
                        if isinstance(index_obj, BTreeIndex | InvertedIndex) and prop_id in index_obj.properties:
                            index.append(index_name)
                    unique_constraints: list[str] = []
                    for constraint_name, constraint_obj in (container.constraints or {}).items():
                        if isinstance(constraint_obj, dm.RequiresConstraint):
                            # This is handled in the .from_container method of DMSContainer
                            continue
                        elif (
                            isinstance(constraint_obj, dm.UniquenessConstraint) and prop_id in constraint_obj.properties
                        ):
                            unique_constraints.append(constraint_name)
                        elif isinstance(constraint_obj, dm.UniquenessConstraint):
                            # This does not apply to this property
                            continue
                        else:
                            raise NotImplementedError(f"Constraint type {type(constraint_obj)} not implemented")

                    if isinstance(container_prop.type, dm.DirectRelation):
                        direct_value_type: str | ViewEntity | DataType | DMSUnknownEntity
                        if prop.source is None:
                            issue_list.append(
                                issues.importing.UnknownValueTypeWarning(class_entity.versioned_id, prop_id)
                            )
                            direct_value_type = DMSUnknownEntity()
                        else:
                            direct_value_type = ViewEntity.from_id(prop.source)

                        dms_property = DMSProperty(
                            class_=class_entity,
                            property_=prop_id,
                            description=prop.description,
                            name=prop.name,
                            value_type=direct_value_type,
                            relation="direct",
                            nullable=container_prop.nullable,
                            default=container_prop.default_value,
                            is_list=False,
                            container=ContainerEntity.from_id(container.as_id()),
                            container_property=prop.container_property_identifier,
                            view=ViewEntity.from_id(view.as_id()),
                            view_property=prop_id,
                            index=index or None,
                            constraint=unique_constraints or None,
                        )
                    else:
                        dms_property = DMSProperty(
                            class_=ClassEntity(prefix=view.space, suffix=view.external_id, version=view.version),
                            property_=prop_id,
                            description=prop.description,
                            name=prop.name,
                            value_type=cast(ViewPropertyEntity | DataType, container_prop.type._type),
                            nullable=container_prop.nullable,
                            is_list=container_prop.type.is_list,
                            default=container_prop.default_value,
                            container=ContainerEntity.from_id(container.as_id()),
                            container_property=prop.container_property_identifier,
                            view=ViewEntity.from_id(view.as_id()),
                            view_property=prop_id,
                            index=index or None,
                            constraint=unique_constraints or None,
                        )
                elif isinstance(prop, dm.MultiEdgeConnectionApply):
                    view_entity = ViewEntity.from_id(prop.source)
                    dms_property = DMSProperty(
                        class_=ClassEntity(prefix=view.space, suffix=view.external_id, version=view.version),
                        property_=prop_id,
                        relation="multiedge",
                        description=prop.description,
                        name=prop.name,
                        value_type=view_entity,
                        view=ViewEntity.from_id(view.as_id()),
                        view_property=prop_id,
                    )
                else:
                    raise NotImplementedError(f"Property type {type(prop)} not implemented")

                properties.append(dms_property)

        data_model_view_ids: set[dm.ViewId] = {
            view.as_id() if isinstance(view, dm.View | dm.ViewApply) else view for view in data_model.views or []
        }

        dms_rules = DMSRules(
            metadata=self.metadata or DMSMetadata.from_data_model(data_model),
            properties=properties,
            containers=SheetList[DMSContainer](
                data=[DMSContainer.from_container(container) for container in self.schema.containers]
            ),
            views=SheetList[DMSView](data=[DMSView.from_view(view, data_model_view_ids) for view in self.schema.views]),
        )
        output_rules: Rules
        if role is RoleTypes.information_architect:
            output_rules = dms_rules.as_information_architect_rules()
        else:
            output_rules = dms_rules
        if errors == "raise":
            return output_rules
        else:
            return output_rules, issue_list
