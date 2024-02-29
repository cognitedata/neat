from typing import cast

from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.containers import BTreeIndex, InvertedIndex
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType

from cognite.neat.rules.models._rules import DMSRules, DMSSchema
from cognite.neat.rules.models._rules._types import ContainerEntity, DMSValueType, ViewEntity
from cognite.neat.rules.models._rules.dms_architect_rules import (
    DMSContainer,
    DMSMetadata,
    DMSProperty,
    DMSView,
    SheetList,
)

from ._base import BaseImporter


class DMSImporter(BaseImporter):
    def __init__(self, schema: DMSSchema):
        self.schema = schema

    def to_rules(self) -> DMSRules:
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
                        if prop.source is None:
                            direct_value_type = "UNKNOWN"
                        else:
                            direct_value_type = prop.source.external_id
                        dms_property = DMSProperty(
                            class_=view.external_id,
                            property_=prop_id,
                            description=prop.description,
                            value_type=cast(ViewEntity | DMSValueType, direct_value_type),
                            relation="direct",
                            nullable=container_prop.nullable if container_prop.nullable is not None else True,
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
                            class_=view.external_id,
                            property_=prop_id,
                            description=prop.description,
                            value_type=cast(ViewEntity | DMSValueType, container_prop.type._type),
                            nullable=container_prop.nullable if container_prop.nullable is not None else True,
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
                    dms_property = DMSProperty(
                        class_=view.external_id,
                        property_=prop_id,
                        relation="multiedge",
                        description=prop.description,
                        value_type=cast(ViewEntity | DMSValueType, prop.source.external_id),
                        is_list=True,
                        nullable=False,
                        view=ViewEntity.from_id(view.as_id()),
                        view_property=prop_id,
                    )
                else:
                    raise NotImplementedError(f"Property type {type(prop)} not implemented")

                properties.append(dms_property)

        return DMSRules(
            metadata=DMSMetadata.from_data_model(data_model),
            properties=properties,
            containers=SheetList[DMSContainer](
                data=[DMSContainer.from_container(container) for container in self.schema.containers]
            ),
            views=SheetList[DMSView](data=[DMSView.from_view(view) for view in self.schema.views]),
        )
