import json
import sys
import warnings
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar, cast

import yaml
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes import DatabaseWrite, DatabaseWriteList, TransformationWrite, TransformationWriteList
from cognite.client.data_classes.data_modeling import ViewApply
from cognite.client.data_classes.transformations.common import Edges, EdgeType, Nodes, ViewInfo

from cognite.neat.rules import issues
from cognite.neat.rules.issues.dms import (
    ContainerPropertyUsedMultipleTimesError,
    DirectRelationMissingSourceWarning,
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
from cognite.neat.rules.models.data_types import _DATA_TYPE_BY_DMS_TYPE
from cognite.neat.utils.cdf_loaders import ViewLoader
from cognite.neat.utils.cdf_loaders.data_classes import RawTableWrite, RawTableWriteList
from cognite.neat.utils.text import to_camel

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


@dataclass
class DMSSchema:
    spaces: dm.SpaceApplyList = field(default_factory=lambda: dm.SpaceApplyList([]))
    data_models: dm.DataModelApplyList = field(default_factory=lambda: dm.DataModelApplyList([]))
    views: dm.ViewApplyList = field(default_factory=lambda: dm.ViewApplyList([]))
    containers: dm.ContainerApplyList = field(default_factory=lambda: dm.ContainerApplyList([]))
    node_types: dm.NodeApplyList = field(default_factory=lambda: dm.NodeApplyList([]))
    # The frozen ids are parts of the schema that should not be modified or deleted.
    # This is used the exporting the schema.
    frozen_ids: set[dm.ViewId | dm.ContainerId | dm.NodeId] = field(default_factory=set)

    _FIELD_NAME_BY_RESOURCE_TYPE: ClassVar[dict[str, str]] = {
        "container": "containers",
        "view": "views",
        "datamodel": "data_models",
        "space": "spaces",
        "node": "node_types",
    }

    @classmethod
    def from_model_id(cls, client: CogniteClient, data_model_id: dm.DataModelIdentifier) -> "DMSSchema":
        data_models = client.data_modeling.data_models.retrieve(data_model_id, inline_views=True)
        if len(data_models) == 0:
            raise ValueError(f"Data model {data_model_id} not found")
        data_model = data_models.latest_version()
        return cls.from_data_model(client, data_model)

    @classmethod
    def from_data_model(cls, client: CogniteClient, data_model: dm.DataModel) -> "DMSSchema":
        views = dm.ViewList(data_model.views)
        container_ids = views.referenced_containers()
        containers = client.data_modeling.containers.retrieve(list(container_ids))
        cls._append_referenced_containers(client, containers)

        space_read = client.data_modeling.spaces.retrieve(data_model.space)
        if space_read is None:
            raise ValueError(f"Space {data_model.space} not found")
        space = space_read.as_write()
        data_model_write = data_model.as_write()
        data_model_write.views = list(views.as_write())

        view_loader = ViewLoader(client)
        # We need to include parent views in the schema to make sure that the schema is valid.
        existing_view_ids = set(views.as_ids())
        parent_view_ids = {parent for view in views for parent in view.implements or []}
        parents = view_loader.retrieve_all_parents(list(parent_view_ids - existing_view_ids))
        views.extend([parent for parent in parents if parent.as_id() not in existing_view_ids])

        # Converting views from read to write format requires to account for parents (implements)
        # as the read format contains all properties from all parents, while the write formate should not contain
        # properties from any parents.
        # The ViewLoader as_write method looks up parents and remove properties from them.
        view_write = dm.ViewApplyList([view_loader.as_write(view) for view in views])

        return cls(
            spaces=dm.SpaceApplyList([space]),
            data_models=dm.DataModelApplyList([data_model_write]),
            views=view_write,
            containers=containers.as_write(),
        )

    @classmethod
    def from_directory(cls, directory: str | Path) -> Self:
        """Load a schema from a directory containing YAML files.

        The directory is expected to follow the Cognite-Toolkit convention
        where each file is named as `resource_type.resource_name.yaml`.
        """
        data = cls._read_directory(Path(directory))
        return cls.load(data)

    @classmethod
    def _read_directory(cls, directory: Path) -> dict[str, list[Any]]:
        data: dict[str, Any] = {}
        for yaml_file in directory.rglob("*.yaml"):
            if "." in yaml_file.stem:
                resource_type = yaml_file.stem.rsplit(".", 1)[-1]
                if attr_name := cls._FIELD_NAME_BY_RESOURCE_TYPE.get(resource_type):
                    data.setdefault(attr_name, [])

                    try:
                        # Using CSafeLoader over safe_load for ~10x speedup
                        loaded = yaml.CSafeLoader(yaml_file.read_text()).get_data()
                    except Exception as e:
                        warnings.warn(issues.fileread.InvalidFileFormatWarning(yaml_file, str(e)), stacklevel=2)
                        continue

                    if isinstance(loaded, list):
                        data[attr_name].extend(loaded)
                    else:
                        data[attr_name].append(loaded)
        return data

    def to_directory(
        self,
        directory: str | Path,
        exclude: set[str] | None = None,
        new_line: str | None = "\n",
        encoding: str | None = "utf-8",
    ) -> None:
        """Save the schema to a directory as YAML files. This is compatible with the Cognite-Toolkit convention.

        Args:
            directory (str | Path): The directory to save the schema to.
            exclude (set[str]): A set of attributes to exclude from the output.
            new_line (str): The line endings to use in the output files. Defaults to "\n".
            encoding (str): The encoding to use in the output files. Defaults to "utf-8".
        """
        path_dir = Path(directory)
        exclude_set = exclude or set()
        data_models = path_dir / "data_models"
        data_models.mkdir(parents=True, exist_ok=True)
        if "spaces" not in exclude_set:
            for space in self.spaces:
                (data_models / f"{space.space}.space.yaml").write_text(
                    space.dump_yaml(), newline=new_line, encoding=encoding
                )
        if "data_models" not in exclude_set:
            for model in self.data_models:
                (data_models / f"{model.external_id}.datamodel.yaml").write_text(
                    model.dump_yaml(), newline=new_line, encoding=encoding
                )
        if "views" not in exclude_set and self.views:
            view_dir = data_models / "views"
            view_dir.mkdir(parents=True, exist_ok=True)
            for view in self.views:
                (view_dir / f"{view.external_id}.view.yaml").write_text(
                    view.dump_yaml(), newline=new_line, encoding=encoding
                )
        if "containers" not in exclude_set and self.containers:
            container_dir = data_models / "containers"
            container_dir.mkdir(parents=True, exist_ok=True)
            for container in self.containers:
                (container_dir / f"{container.external_id}.container.yaml").write_text(
                    container.dump_yaml(), newline=new_line, encoding=encoding
                )
        if "node_types" not in exclude_set and self.node_types:
            node_dir = data_models / "nodes"
            node_dir.mkdir(parents=True, exist_ok=True)
            for node in self.node_types:
                (node_dir / f"{node.external_id}.node.yaml").write_text(
                    node.dump_yaml(), newline=new_line, encoding=encoding
                )

    @classmethod
    def from_zip(cls, zip_file: str | Path) -> Self:
        """Load a schema from a ZIP file containing YAML files.

        The ZIP file is expected to follow the Cognite-Toolkit convention
        where each file is named as `resource_type.resource_name.yaml`.
        """
        data = cls._read_zip(Path(zip_file))
        return cls.load(data)

    @classmethod
    def _read_zip(cls, zip_file: Path) -> dict[str, list[Any]]:
        data: dict[str, list[Any]] = {}
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith(".yaml"):
                    if "/" not in file_info.filename:
                        continue
                    filename = Path(file_info.filename.split("/")[-1])
                    if "." not in filename.stem:
                        continue
                    resource_type = filename.stem.rsplit(".", 1)[-1]
                    if attr_name := cls._FIELD_NAME_BY_RESOURCE_TYPE.get(resource_type):
                        data.setdefault(attr_name, [])
                        try:
                            # Using CSafeLoader over safe_load for ~10x speedup
                            loaded = yaml.CSafeLoader(zip_ref.read(file_info).decode()).get_data()
                        except Exception as e:
                            warnings.warn(issues.fileread.InvalidFileFormatWarning(filename, str(e)), stacklevel=2)
                            continue
                        if isinstance(loaded, list):
                            data[attr_name].extend(loaded)
                        else:
                            data[attr_name].append(loaded)
        return data

    def to_zip(self, zip_file: str | Path, exclude: set[str] | None = None) -> None:
        """Save the schema to a ZIP file as YAML files. This is compatible with the Cognite-Toolkit convention.

        Args:
            zip_file (str | Path): The ZIP file to save the schema to.
            exclude (set[str]): A set of attributes to exclude from the output.
        """
        exclude_set = exclude or set()
        with zipfile.ZipFile(zip_file, "w") as zip_ref:
            if "spaces" not in exclude_set:
                for space in self.spaces:
                    zip_ref.writestr(f"data_models/{space.space}.space.yaml", space.dump_yaml())
            if "data_models" not in exclude_set:
                for model in self.data_models:
                    zip_ref.writestr(f"data_models/{model.external_id}.datamodel.yaml", model.dump_yaml())
            if "views" not in exclude_set:
                for view in self.views:
                    zip_ref.writestr(f"data_models/views/{view.external_id}.view.yaml", view.dump_yaml())
            if "containers" not in exclude_set:
                for container in self.containers:
                    zip_ref.writestr(
                        f"data_models/containers{container.external_id}.container.yaml", container.dump_yaml()
                    )
            if "node_types" not in exclude_set:
                for node in self.node_types:
                    zip_ref.writestr(f"data_models/nodes/{node.external_id}.node.yaml", node.dump_yaml())

    @classmethod
    def load(cls, data: str | dict[str, list[Any]]) -> Self:
        if isinstance(data, str):
            # YAML is a superset of JSON, so we can use the same parser
            try:
                # Using CSafeLoader over safe_load for ~10x speedup
                data_dict = yaml.CSafeLoader(data).get_data()
            except Exception as e:
                raise issues.fileread.FailedStringLoadError(".yaml", str(e)) from None
            if not isinstance(data_dict, dict) and all(isinstance(v, list) for v in data_dict.values()):
                raise issues.fileread.FailedStringLoadError(
                    "dict[str, list[Any]]", f"Invalid data structure: {type(data)}"
                ) from None
        else:
            data_dict = data
        loaded: dict[str, Any] = {}
        for attr in fields(cls):
            if items := data_dict.get(attr.name) or data_dict.get(to_camel(attr.name)):
                loaded[attr.name] = attr.type.load(items)
        return cls(**loaded)

    def dump(self, camel_case: bool = True, sort: bool = True) -> dict[str, Any]:
        """Dump the schema to a dictionary that can be serialized to JSON.

        Args:
            camel_case (bool): If True, the keys in the output dictionary will be in camel case.
            sort (bool): If True, the items in the output dictionary will be sorted by their ID.
                This is useful for deterministic output which is useful for comparing schemas.

        Returns:
            dict: The schema as a dictionary.
        """
        output: dict[str, Any] = {}
        cls_fields = sorted(fields(self), key=lambda f: f.name) if sort else fields(self)
        for attr in cls_fields:
            if items := getattr(self, attr.name):
                items = sorted(items, key=self._to_sortable_identifier) if sort else items
                key = to_camel(attr.name) if camel_case else attr.name
                output[key] = [item.dump(camel_case=camel_case) for item in items]
        return output

    @classmethod
    def _to_sortable_identifier(cls, item: Any) -> str | tuple[str, str] | tuple[str, str, str]:
        if isinstance(item, dm.ContainerApply | dm.ViewApply | dm.DataModelApply | dm.NodeApply | RawTableWrite):
            identifier = item.as_id().as_tuple()
            if len(identifier) == 3 and identifier[2] is None:
                return identifier[:2]  # type: ignore[misc]
            return cast(tuple[str, str] | tuple[str, str, str], identifier)
        elif isinstance(item, dm.SpaceApply):
            return item.space
        elif isinstance(item, TransformationWrite):
            return item.external_id or ""
        elif isinstance(item, DatabaseWrite):
            return item.name or ""
        else:
            raise ValueError(f"Cannot sort item of type {type(item)}")

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
                            warnings.warn(
                                DirectRelationMissingSourceWarning(view_id=view_id, property=prop_name), stacklevel=2
                            )

                if isinstance(prop, dm.EdgeConnectionApply) and prop.source not in defined_views:
                    errors.add(MissingSourceViewError(view=prop.source, property=prop_name, referred_by=view_id))

                if (
                    isinstance(prop, dm.EdgeConnectionApply)
                    and prop.edge_source is not None
                    and prop.edge_source not in defined_views
                ):
                    errors.add(MissingEdgeViewError(view=prop.edge_source, property=prop_name, referred_by=view_id))

            # This allows for multiple view properties to be mapped to the same container property,
            # as long as they have different external_id, otherwise this will lead to raising
            # error ContainerPropertyUsedMultipleTimesError
            property_count = Counter(
                (prop.container, prop.container_property_identifier, view_property_identifier)
                for view_property_identifier, prop in (view.properties or {}).items()
                if isinstance(prop, dm.MappedPropertyApply)
            )

            for (
                container_id,
                container_property_identifier,
                _,
            ), count in property_count.items():
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

    @classmethod
    def _append_referenced_containers(cls, client: CogniteClient, containers: dm.ContainerList) -> None:
        """Containers can reference each other through the 'requires' constraint.

        This method retrieves all containers that are referenced by other containers through the 'requires' constraint,
        including their parents.

        """
        for _ in range(10):  # Limiting the number of iterations to avoid infinite loops
            referenced_containers = {
                const.require
                for container in containers
                for const in (container.constraints or {}).values()
                if isinstance(const, dm.RequiresConstraint)
            }
            missing_containers = referenced_containers - set(containers.as_ids())
            if not missing_containers:
                break
            found_containers = client.data_modeling.containers.retrieve(list(missing_containers))
            containers.extend(found_containers)
            if len(found_containers) != len(missing_containers):
                break
        else:
            warnings.warn(
                "The maximum number of iterations was reached while resolving referenced containers."
                "There might be referenced containers that are not included in the list of containers.",
                RuntimeWarning,
                stacklevel=2,
            )
        return None

    def referenced_spaces(self) -> set[str]:
        referenced_spaces = {container.space for container in self.containers}
        referenced_spaces |= {view.space for view in self.views}
        referenced_spaces |= {container.space for view in self.views for container in view.referenced_containers()}
        referenced_spaces |= {parent.space for view in self.views for parent in view.implements or []}
        referenced_spaces |= {node.space for node in self.node_types}
        referenced_spaces |= {model.space for model in self.data_models}
        referenced_spaces |= {view.space for model in self.data_models for view in model.views or []}
        referenced_spaces |= {s.space for s in self.spaces}

        return referenced_spaces


@dataclass
class PipelineSchema(DMSSchema):
    transformations: TransformationWriteList = field(default_factory=lambda: TransformationWriteList([]))
    databases: DatabaseWriteList = field(default_factory=lambda: DatabaseWriteList([]))
    raw_tables: RawTableWriteList = field(default_factory=lambda: RawTableWriteList([]))

    _FIELD_NAME_BY_RESOURCE_TYPE: ClassVar[dict[str, str]] = {
        **DMSSchema._FIELD_NAME_BY_RESOURCE_TYPE,
        "raw": "raw_tables",
    }

    def __post_init__(self):
        existing_databases = {database.name for database in self.databases}
        table_database = {table.database for table in self.raw_tables}
        if missing := table_database - existing_databases:
            self.databases.extend([DatabaseWrite(name=database) for database in missing])

    @classmethod
    def _read_directory(cls, directory: Path) -> dict[str, list[Any]]:
        data = super()._read_directory(directory)
        for yaml_file in directory.rglob("*.yaml"):
            if yaml_file.parent.name in ("transformations", "raw"):
                attr_name = cls._FIELD_NAME_BY_RESOURCE_TYPE.get(yaml_file.parent.name, yaml_file.parent.name)
                data.setdefault(attr_name, [])
                loaded = yaml.safe_load(yaml_file.read_text())
                if isinstance(loaded, list):
                    data[attr_name].extend(loaded)
                else:
                    data[attr_name].append(loaded)
        return data

    def to_directory(
        self,
        directory: str | Path,
        exclude: set[str] | None = None,
        new_line: str | None = "\n",
        encoding: str | None = "utf-8",
    ) -> None:
        super().to_directory(directory, exclude)
        exclude_set = exclude or set()
        path_dir = Path(directory)
        if "transformations" not in exclude_set and self.transformations:
            transformation_dir = path_dir / "transformations"
            transformation_dir.mkdir(exist_ok=True, parents=True)
            for transformation in self.transformations:
                (transformation_dir / f"{transformation.external_id}.yaml").write_text(
                    transformation.dump_yaml(), newline=new_line, encoding=encoding
                )
        if "raw" not in exclude_set and self.raw_tables:
            # The RAW Databases are not written to file. This is because cognite-toolkit expects the RAW databases
            # to be in the same file as the RAW tables.
            raw_dir = path_dir / "raw"
            raw_dir.mkdir(exist_ok=True, parents=True)
            for raw_table in self.raw_tables:
                (raw_dir / f"{raw_table.name}.yaml").write_text(
                    raw_table.dump_yaml(), newline=new_line, encoding=encoding
                )

    def to_zip(self, zip_file: str | Path, exclude: set[str] | None = None) -> None:
        super().to_zip(zip_file, exclude)
        exclude_set = exclude or set()
        with zipfile.ZipFile(zip_file, "a") as zip_ref:
            if "transformations" not in exclude_set:
                for transformation in self.transformations:
                    zip_ref.writestr(f"transformations/{transformation.external_id}.yaml", transformation.dump_yaml())
            if "raw" not in exclude_set:
                # The RAW Databases are not written to file. This is because cognite-toolkit expects the RAW databases
                # to be in the same file as the RAW tables.
                for raw_table in self.raw_tables:
                    zip_ref.writestr(f"raw/{raw_table.name}.yaml", raw_table.dump_yaml())

    @classmethod
    def _read_zip(cls, zip_file: Path) -> dict[str, list[Any]]:
        data = super()._read_zip(zip_file)
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith(".yaml"):
                    if "/" not in file_info.filename:
                        continue
                    filepath = Path(file_info.filename)
                    if (parent := filepath.parent.name) in ("transformations", "raw"):
                        attr_name = cls._FIELD_NAME_BY_RESOURCE_TYPE.get(parent, parent)
                        data.setdefault(attr_name, [])
                        loaded = yaml.safe_load(zip_ref.read(file_info).decode())
                        if isinstance(loaded, list):
                            data[attr_name].extend(loaded)
                        else:
                            data[attr_name].append(loaded)
        return data

    @classmethod
    def from_dms(cls, schema: DMSSchema, instance_space: str | None = None) -> "PipelineSchema":
        if not schema.data_models:
            raise ValueError("PipelineSchema must contain at least one data model")
        first_data_model = schema.data_models[0]
        # The database name is limited to 32 characters
        database_name = first_data_model.external_id[:32]
        instance_space = instance_space or first_data_model.space
        database = DatabaseWrite(name=database_name)
        parent_views = {parent for view in schema.views for parent in view.implements or []}
        container_by_id = {container.as_id(): container for container in schema.containers}

        transformations = TransformationWriteList([])
        raw_tables = RawTableWriteList([])
        for view in schema.views:
            if view.as_id() in parent_views:
                # Skipping parents as they do not have their own data
                continue
            mapped_properties = {
                prop_name: prop
                for prop_name, prop in (view.properties or {}).items()
                if isinstance(prop, dm.MappedPropertyApply)
            }
            if mapped_properties:
                view_table = RawTableWrite(name=f"{view.external_id}Properties", database=database_name)
                raw_tables.append(view_table)
                transformation = cls._create_property_transformation(
                    mapped_properties, view, view_table, container_by_id, instance_space
                )
                transformations.append(transformation)
            connection_properties = {
                prop_name: prop
                for prop_name, prop in (view.properties or {}).items()
                if isinstance(prop, dm.EdgeConnectionApply)
            }
            for prop_name, connection_property in connection_properties.items():
                view_table = RawTableWrite(name=f"{view.external_id}.{prop_name}Edge", database=database_name)
                raw_tables.append(view_table)
                transformation = cls._create_edge_transformation(connection_property, view, view_table, instance_space)
                transformations.append(transformation)

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
        cls,
        properties: dict[str, dm.MappedPropertyApply],
        view: ViewApply,
        table: RawTableWrite,
        container_by_id: dict[dm.ContainerId, dm.ContainerApply],
        instance_space: str,
    ) -> TransformationWrite:
        mapping_mode = {
            "version": 1,
            "sourceType": "raw",
            # 'mappings' is set here and overwritten further down to ensure the correct order
            "mappings": [],
            "sourceLevel1": table.database,
            "sourceLevel2": table.name,
        }
        mappings = [
            {"from": "externalId", "to": "externalId", "asType": "STRING"},
        ]
        select_rows = ["cast(`externalId` as STRING) as externalId"]
        for prop_name, prop in properties.items():
            container = container_by_id.get(prop.container)
            if container is not None:
                dms_type = container.properties[prop.container_property_identifier].type._type
                if dms_type in _DATA_TYPE_BY_DMS_TYPE:
                    sql_type = _DATA_TYPE_BY_DMS_TYPE[dms_type].sql
                else:
                    warnings.warn(
                        f"Unknown DMS type '{dms_type}' for property '{prop_name}'", RuntimeWarning, stacklevel=2
                    )
                    sql_type = "STRING"
            else:
                sql_type = "STRING"
            select_rows.append(f"cast(`{prop_name}` as {sql_type}) as {prop_name}")
            mappings.append({"from": prop_name, "to": prop_name, "asType": sql_type})
        mapping_mode["mappings"] = mappings
        select = ",\n  ".join(select_rows)

        return TransformationWrite(
            external_id=f"{table.name}Transformation",
            name=f"{table.name}Transformation",
            ignore_null_fields=True,
            destination=Nodes(
                view=ViewInfo(view.space, view.external_id, view.version),
                instance_space=instance_space,
            ),
            conflict_mode="upsert",
            query=f"""/* MAPPING_MODE_ENABLED: true */
/* {json.dumps(mapping_mode)} */
select
  {select}
from
  `{table.database}`.`{table.name}`;
""",
        )

    @classmethod
    def _create_edge_transformation(
        cls, property_: dm.EdgeConnectionApply, view: ViewApply, table: RawTableWrite, instance_space: str
    ) -> TransformationWrite:
        start, end = view.external_id, property_.source.external_id
        if property_.direction == "inwards":
            start, end = end, start
        mapping_mode = {
            "version": 1,
            "sourceType": "raw",
            "mappings": [
                {"from": "externalId", "to": "externalId", "asType": "STRING"},
                {"from": start, "to": "startNode", "asType": "STRUCT<`space`:STRING, `externalId`:STRING>"},
                {"from": end, "to": "endNode", "asType": "STRUCT<`space`:STRING, `externalId`:STRING>"},
            ],
            "sourceLevel1": table.database,
            "sourceLevel2": table.name,
        }
        select_rows = [
            "cast(`externalId` as STRING) as externalId",
            f"node_reference('{instance_space}', `{start}`) as startNode",
            f"node_reference('{instance_space}', `{end}`) as endNode",
        ]
        select = ",\n  ".join(select_rows)

        return TransformationWrite(
            external_id=f"{table.name}Transformation",
            name=f"{table.name}Transformation",
            ignore_null_fields=True,
            destination=Edges(
                instance_space=instance_space,
                edge_type=EdgeType(space=property_.type.space, external_id=property_.type.external_id),
            ),
            conflict_mode="upsert",
            query=f"""/* MAPPING_MODE_ENABLED: true */
/* {json.dumps(mapping_mode)} */
select
  {select}
from
  `{table.database}`.`{table.name}`;
""",
        )
