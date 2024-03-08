from typing import Literal, cast, overload

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling import DataModelIdentifier
from cognite.client.data_classes.data_modeling.containers import BTreeIndex, InvertedIndex
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType

from cognite.neat.rules.models._rules import DMSRules, DMSSchema, RoleTypes
from cognite.neat.rules.models._rules._types import ClassEntity, ContainerEntity, DMSValueType, ViewEntity
from cognite.neat.rules.models._rules.dms_architect_rules import (
    DMSContainer,
    DMSMetadata,
    DMSProperty,
    DMSView,
    SheetList,
)
from cognite.neat.rules.validation import IssueList

from ._base import BaseImporter, Rules


class DMSImporter(BaseImporter):
    def __init__(self, schema: DMSSchema):
        self.schema = schema

    @classmethod
    def from_data_model_id(cls, client: CogniteClient, data_model_id: DataModelIdentifier) -> "DMSImporter":
        return cls(DMSSchema.from_model_id(client, data_model_id))

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
        data_model = self.schema.data_models[0]

        container_by_id = {container.as_id(): container for container in self.schema.containers}

        properties = SheetList[DMSProperty]()
        for view in self.schema.views:
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
                        direct_value_type: str | ViewEntity | DMSValueType
                        if prop.source is None:
                            direct_value_type = "UNKNOWN"
                        else:
                            direct_value_type = ViewEntity.from_id(prop.source)
                        dms_property = DMSProperty(
                            class_=ClassEntity(prefix=view.space, suffix=view.external_id, version=view.version),
                            property_=prop_id,
                            description=prop.description,
                            value_type=cast(ViewEntity | DMSValueType, direct_value_type),
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
                            value_type=cast(ViewEntity | DMSValueType, container_prop.type._type),
                            nullable=container_prop.nullable,
                            is_list=(
                                container_prop.type.is_list
                                if isinstance(container_prop.type, ListablePropertyType)
                                else False
                            ),
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
                        value_type=view_entity,
                        view=ViewEntity.from_id(view.as_id()),
                        view_property=prop_id,
                    )
                else:
                    raise NotImplementedError(f"Property type {type(prop)} not implemented")

                properties.append(dms_property)

        dms_rules = DMSRules(
            metadata=DMSMetadata.from_data_model(data_model),
            properties=properties,
            containers=SheetList[DMSContainer](
                data=[DMSContainer.from_container(container) for container in self.schema.containers]
            ),
            views=SheetList[DMSView](data=[DMSView.from_view(view) for view in self.schema.views]),
        )
        output_rules: Rules
        if role is RoleTypes.information_architect:
            output_rules = dms_rules.as_information_architect_rules()
        else:
            output_rules = dms_rules
        if errors == "raise":
            return output_rules
        else:
            return output_rules, IssueList()
