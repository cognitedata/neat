from collections import Counter, defaultdict
from dataclasses import dataclass, field

from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes import DatabaseWrite, DatabaseWriteList, TransformationWrite, TransformationWriteList
from cognite.client.data_classes.data_modeling import ViewApply
from cognite.client.data_classes.transformations.common import Nodes, ViewInfo

from cognite.neat.rules.issues.dms import (
    ContainerPropertyUsedMultipleTimesError,
    DirectRelationMissingSourceError,
    DMSSchemaError,
    DuplicatedViewInDataModelError,
    MissingContainerError,
    MissingContainerPropertyError,
    MissingEdgeViewError,
    MissingParentViewError,
    MissingSourceViewError,
    MissingSpaceError,
    MissingViewError,
)
from cognite.neat.utils.cdf_loaders import ViewLoader
from cognite.neat.utils.cdf_loaders.data_classes import RawTableWrite, RawTableWriteList


@dataclass
class DMSSchema:
    spaces: dm.SpaceApplyList = field(default_factory=lambda: dm.SpaceApplyList([]))
    data_models: dm.DataModelApplyList = field(default_factory=lambda: dm.DataModelApplyList([]))
    views: dm.ViewApplyList = field(default_factory=lambda: dm.ViewApplyList([]))
    containers: dm.ContainerApplyList = field(default_factory=lambda: dm.ContainerApplyList([]))
    node_types: dm.NodeApplyList = field(default_factory=lambda: dm.NodeApplyList([]))

    @classmethod
    def from_model_id(cls, client: CogniteClient, data_model_id: dm.DataModelIdentifier) -> "DMSSchema":
        data_models = client.data_modeling.data_models.retrieve(data_model_id, inline_views=True)
        if len(data_models) == 0:
            raise ValueError(f"Data model {data_model_id} not found")
        data_model = data_models.latest_version()
        views = dm.ViewList(data_model.views)
        container_ids = views.referenced_containers()
        containers = client.data_modeling.containers.retrieve(list(container_ids))
        space_read = client.data_modeling.spaces.retrieve(data_model.space)
        if space_read is None:
            raise ValueError(f"Space {data_model.space} not found")
        space = space_read.as_write()
        data_model_write = data_model.as_write()
        data_model_write.views = list(views.as_write())

        # Converting views from read to write format requires to account for parents (implements)
        # as the read format contains all properties from all parents, while the write formate should not contain
        # properties from any parents.
        # The ViewLoader as_write method looks up parents and remove properties from them.
        view_loader = ViewLoader(client)
        view_write = dm.ViewApplyList([view_loader.as_write(view) for view in views])

        return cls(
            spaces=dm.SpaceApplyList([space]),
            data_models=dm.DataModelApplyList([data_model_write]),
            views=view_write,
            containers=containers.as_write(),
        )

    def validate(self) -> list[DMSSchemaError]:
        errors: set[DMSSchemaError] = set()
        defined_spaces = {space.space for space in self.spaces}
        defined_containers = {container.as_id(): container for container in self.containers}
        defined_views = {view.as_id() for view in self.views}

        for container in self.containers:
            if container.space not in defined_spaces:
                errors.add(MissingSpaceError(space=container.space, referred_by=container.as_id()))

        for view in self.views:
            view_id = view.as_id()
            if view.space not in defined_spaces:
                errors.add(MissingSpaceError(space=view.space, referred_by=view_id))

            for parent in view.implements or []:
                if parent not in defined_views:
                    errors.add(MissingParentViewError(view=parent, referred_by=view_id))

            for prop_name, prop in (view.properties or {}).items():
                if isinstance(prop, dm.MappedPropertyApply):
                    ref_container = defined_containers.get(prop.container)
                    if ref_container is None:
                        errors.add(MissingContainerError(container=prop.container, referred_by=view_id))
                    elif prop.container_property_identifier not in ref_container.properties:
                        errors.add(
                            MissingContainerPropertyError(
                                container=prop.container,
                                property=prop.container_property_identifier,
                                referred_by=view_id,
                            )
                        )
                    else:
                        container_property = ref_container.properties[prop.container_property_identifier]

                        if isinstance(container_property.type, dm.DirectRelation) and prop.source is None:
                            errors.add(DirectRelationMissingSourceError(view_id=view_id, property=prop_name))

                if isinstance(prop, dm.EdgeConnectionApply) and prop.source not in defined_views:
                    errors.add(MissingSourceViewError(view=prop.source, property=prop_name, referred_by=view_id))

                if (
                    isinstance(prop, dm.EdgeConnectionApply)
                    and prop.edge_source is not None
                    and prop.edge_source not in defined_views
                ):
                    errors.add(MissingEdgeViewError(view=prop.edge_source, property=prop_name, referred_by=view_id))

            property_count = Counter(
                (prop.container, prop.container_property_identifier)
                for prop in (view.properties or {}).values()
                if isinstance(prop, dm.MappedPropertyApply)
            )
            for (container_id, container_property_identifier), count in property_count.items():
                if count > 1:
                    view_properties = [
                        prop_name
                        for prop_name, prop in (view.properties or {}).items()
                        if isinstance(prop, dm.MappedPropertyApply)
                        and (prop.container, prop.container_property_identifier)
                        == (container_id, container_property_identifier)
                    ]
                    errors.add(
                        ContainerPropertyUsedMultipleTimesError(
                            container=container_id,
                            property=container_property_identifier,
                            referred_by=frozenset({(view_id, prop_name) for prop_name in view_properties}),
                        )
                    )

        for model in self.data_models:
            if model.space not in defined_spaces:
                errors.add(MissingSpaceError(space=model.space, referred_by=model.as_id()))

            view_counts: dict[dm.ViewId, int] = defaultdict(int)
            for view_id_or_class in model.views or []:
                view_id = view_id_or_class if isinstance(view_id_or_class, dm.ViewId) else view_id_or_class.as_id()
                if view_id not in defined_views:
                    errors.add(MissingViewError(referred_by=model.as_id(), view=view_id))
                view_counts[view_id] += 1

            for view_id, count in view_counts.items():
                if count > 1:
                    errors.add(DuplicatedViewInDataModelError(referred_by=model.as_id(), view=view_id))

        return list(errors)


@dataclass
class PipelineSchema(DMSSchema):
    transformations: TransformationWriteList = field(default_factory=lambda: TransformationWriteList([]))
    databases: DatabaseWriteList = field(default_factory=lambda: DatabaseWriteList([]))
    raw_tables: RawTableWriteList = field(default_factory=lambda: RawTableWriteList([]))

    @classmethod
    def from_dms(cls, schema: DMSSchema) -> "PipelineSchema":
        if not schema.data_models:
            raise ValueError("PipelineSchema must contain at least one data model")
        first_data_model = schema.data_models[0]
        # The database name is limited to 32 characters
        database_name = first_data_model.external_id[:32]
        database = DatabaseWrite(name=database_name)
        parent_views = {parent for view in schema.views for parent in view.implements or []}
        transformations = TransformationWriteList([])
        raw_tables = RawTableWriteList([])
        for view in schema.views:
            if view.as_id() in parent_views:
                # Skipping parents as they do not have their own data
                continue
            mapped_properties = [
                prop for prop in (view.properties or {}).values() if isinstance(prop, dm.MappedPropertyApply)
            ]
            if mapped_properties:
                view_table = RawTableWrite(name=f"{view.external_id}Properties", database=database_name)
                raw_tables.append(view_table)

            connection_properties = {
                prop_name: prop
                for prop_name, prop in (view.properties or {}).items()
                if isinstance(prop, dm.EdgeConnectionApply)
            }
            for prop_name, _connection_property in (connection_properties or {}).items():
                view_table = RawTableWrite(name=f"{view.external_id}To{prop_name}Connection", database=database_name)
                raw_tables.append(view_table)

        return cls(
            spaces=schema.spaces,
            data_models=schema.data_models,
            views=schema.views,
            containers=schema.containers,
            transformations=transformations,
            databases=DatabaseWriteList([database]),
            raw_tables=raw_tables,
        )

    @classmethod
    def _create_property_transformation(
        cls, properties: list[dm.MappedPropertyApply], view: ViewApply, table: RawTableWrite
    ) -> TransformationWrite:
        return TransformationWrite(
            external_id=f"{table.name}Transformation",
            name=f"{table.name}Transformation",
            ignore_null_fields=True,
            destination=Nodes(
                view=ViewInfo(view.space, view.external_id, view.version),
                instance_space=table.database,
            ),
            conflict_mode="upsert",
            query="""
SELECT

""",
        )

    @classmethod
    def _create_connection_transformation(
        cls, properties: list[dm.EdgeConnectionApply], view: ViewApply, table: RawTableWrite
    ) -> TransformationWrite:
        return TransformationWrite(
            external_id=f"{table.name}Transformation",
            name=f"{table.name}Transformation",
            ignore_null_fields=True,
            destination=Nodes(
                view=ViewInfo(view.space, view.external_id, view.version),
                instance_space=table.database,
            ),
            conflict_mode="upsert",
            query="""
SELECT

""",
        )
