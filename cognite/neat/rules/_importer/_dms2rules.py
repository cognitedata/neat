from cognite.client import data_modeling as dm
from cognite.client.data_classes.data_modeling.containers import BTreeIndex, InvertedIndex
from cognite.client.data_classes.data_modeling.data_types import ListablePropertyType

from cognite.neat.rules.models._rules import DMSRules, DMSSchema
from cognite.neat.rules.models._rules._types import ContainerEntity, ViewEntity
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

                    index: str | None = None
                    for index_name, index_obj in (container.indexes or {}).items():
                        if isinstance(index_obj, BTreeIndex | InvertedIndex) and container_prop in index_obj.properties:
                            index = index_name
                            break
                    constraint: str | None = None
                    if container.constraints:
                        raise NotImplementedError("Constraints not implemented")

                    dms_property = DMSProperty(
                        class_=view.external_id,
                        property_=prop_id,
                        description=prop.description,
                        value_type=container_prop.type._type,
                        nullable=container_prop.nullable,
                        is_list=container_prop.type.is_list
                        if isinstance(container_prop.type, ListablePropertyType)
                        else None,
                        default=container_prop.default_value,
                        container=ContainerEntity.from_id(container.as_id()),
                        container_property=prop.container_property_identifier,
                        view=ViewEntity.from_id(view.as_id()),
                        view_property=prop_id,
                        index=index,
                        constraint=constraint,
                    )
                elif isinstance(prop, dm.MultiEdgeConnectionApply):
                    dms_property = DMSProperty(
                        class_=view.external_id,
                        property_=prop_id,
                        description=prop.description,
                        value_type=prop.source.external_id,
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
