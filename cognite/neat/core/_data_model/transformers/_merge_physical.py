from cognite.neat.core._data_model.models import DMSRules, SheetList
from cognite.neat.core._data_model.models.data_types import Enum
from cognite.neat.core._data_model.models.dms import DMSContainer, DMSEnum, DMSNode
from cognite.neat.core._data_model.transformers import VerifiedRulesTransformer


class MergeDMSRules(VerifiedRulesTransformer[DMSRules, DMSRules]):
    def __init__(self, extra: DMSRules) -> None:
        self.extra = extra

    def transform(self, rules: DMSRules) -> DMSRules:
        output = rules.model_copy(deep=True)
        existing_views = {view.view for view in output.views}
        for view in self.extra.views:
            if view.view not in existing_views:
                output.views.append(view)
        existing_properties = {(prop.view, prop.view_property) for prop in output.properties}
        existing_containers = {container.container for container in output.containers or []}
        existing_enum_collections = {collection.collection for collection in output.enum or []}
        new_containers_by_entity = {container.container: container for container in self.extra.containers or []}
        new_enum_collections_by_entity = {collection.collection: collection for collection in self.extra.enum or []}
        for prop in self.extra.properties:
            if (prop.view, prop.view_property) in existing_properties:
                continue
            output.properties.append(prop)
            if prop.container and prop.container not in existing_containers:
                if output.containers is None:
                    output.containers = SheetList[DMSContainer]()
                output.containers.append(new_containers_by_entity[prop.container])
                existing_containers.add(prop.container)
            if isinstance(prop.value_type, Enum) and prop.value_type.collection not in existing_enum_collections:
                if output.enum is None:
                    output.enum = SheetList[DMSEnum]()
                output.enum.append(new_enum_collections_by_entity[prop.value_type.collection])
                existing_enum_collections.add(prop.value_type.collection)

        existing_nodes = {node.node for node in output.nodes or []}
        for node in self.extra.nodes or []:
            if node.node not in existing_nodes:
                if output.nodes is None:
                    output.nodes = SheetList[DMSNode]()
                output.nodes.append(node)
                existing_nodes.add(node.node)

        return output

    @property
    def description(self) -> str:
        return f"Merged with {self.extra.metadata.as_data_model_id()}"
