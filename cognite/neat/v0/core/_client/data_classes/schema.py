import sys
import warnings
import zipfile
from collections import ChainMap
from collections.abc import Iterable, MutableMapping
from dataclasses import Field, dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar, Literal, cast

import yaml
from cognite.client import data_modeling as dm
from cognite.client.data_classes import DatabaseWrite, TransformationWrite
from cognite.client.data_classes.data_modeling.views import (
    ReverseDirectRelationApply,
    SingleEdgeConnection,
    SingleEdgeConnectionApply,
    SingleReverseDirectRelation,
    SingleReverseDirectRelationApply,
    ViewProperty,
    ViewPropertyApply,
)

from cognite.neat.v0.core._client.data_classes.data_modeling import (
    CogniteResourceDict,
    ContainerApplyDict,
    NodeApplyDict,
    SpaceApplyDict,
    ViewApplyDict,
)
from cognite.neat.v0.core._issues.errors import (
    NeatYamlError,
)
from cognite.neat.v0.core._issues.warnings import (
    FileTypeUnexpectedWarning,
    ResourcesDuplicatedWarning,
)
from cognite.neat.v0.core._utils.text import to_camel_case

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


@dataclass
class DMSSchema:
    data_model: dm.DataModelApply | None = None
    spaces: SpaceApplyDict = field(default_factory=SpaceApplyDict)
    views: ViewApplyDict = field(default_factory=ViewApplyDict)
    containers: ContainerApplyDict = field(default_factory=ContainerApplyDict)
    node_types: NodeApplyDict = field(default_factory=NodeApplyDict)

    _FIELD_NAME_BY_RESOURCE_TYPE: ClassVar[dict[str, str]] = {
        "container": "containers",
        "view": "views",
        "datamodel": "data_model",
        "space": "spaces",
        "node": "node_types",
    }

    @classmethod
    def from_directory(cls, directory: str | Path) -> Self:
        """Load a schema from a directory containing YAML files.

        The directory is expected to follow the Cognite-Toolkit convention
        where each file is named as `resource_type.resource_name.yaml`.
        """
        data, context = cls._read_directory(Path(directory))
        return cls.load(data, context)

    @classmethod
    def _read_directory(cls, directory: Path) -> tuple[dict[str, list[Any]], dict[str, list[Path]]]:
        data: dict[str, Any] = {}
        context: dict[str, list[Path]] = {}
        for yaml_file in directory.rglob("*.yaml"):
            if "." in yaml_file.stem:
                resource_type = yaml_file.stem.rsplit(".", 1)[-1]
                if attr_name := cls._FIELD_NAME_BY_RESOURCE_TYPE.get(resource_type):
                    data.setdefault(attr_name, [])
                    context.setdefault(attr_name, [])
                    try:
                        loaded = yaml.safe_load(yaml_file.read_text())
                    except Exception as e:
                        warnings.warn(
                            FileTypeUnexpectedWarning(yaml_file, frozenset([".yaml", ".yml"]), str(e)), stacklevel=2
                        )
                        continue

                    if isinstance(loaded, list):
                        data[attr_name].extend(loaded)
                        context[attr_name].extend([yaml_file] * len(loaded))
                    else:
                        data[attr_name].append(loaded)
                        context[attr_name].append(yaml_file)
        return data, context

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
            for space in self.spaces.values():
                (data_models / f"{space.space}.space.yaml").write_text(
                    space.dump_yaml(), newline=new_line, encoding=encoding
                )
        if "data_models" not in exclude_set and self.data_model:
            (data_models / f"{self.data_model.external_id}.datamodel.yaml").write_text(
                self.data_model.dump_yaml(), newline=new_line, encoding=encoding
            )
        if "views" not in exclude_set and self.views:
            view_dir = data_models / "views"
            view_dir.mkdir(parents=True, exist_ok=True)
            for view in self.views.values():
                (view_dir / f"{view.external_id}.view.yaml").write_text(
                    view.dump_yaml(), newline=new_line, encoding=encoding
                )
        if "containers" not in exclude_set and self.containers:
            container_dir = data_models / "containers"
            container_dir.mkdir(parents=True, exist_ok=True)
            for container in self.containers.values():
                (container_dir / f"{container.external_id}.container.yaml").write_text(
                    container.dump_yaml(), newline=new_line, encoding=encoding
                )
        if "node_types" not in exclude_set and self.node_types:
            node_dir = data_models / "nodes"
            node_dir.mkdir(parents=True, exist_ok=True)
            for node in self.node_types.values():
                (node_dir / f"{node.external_id}.node.yaml").write_text(
                    node.dump_yaml(), newline=new_line, encoding=encoding
                )

    @classmethod
    def from_zip(cls, zip_file: str | Path) -> Self:
        """Load a schema from a ZIP file containing YAML files.

        The ZIP file is expected to follow the Cognite-Toolkit convention
        where each file is named as `resource_type.resource_name.yaml`.
        """
        data, context = cls._read_zip(Path(zip_file))
        return cls.load(data, context)

    @classmethod
    def _read_zip(cls, zip_file: Path) -> tuple[dict[str, list[Any]], dict[str, list[Path]]]:
        data: dict[str, list[Any]] = {}
        context: dict[str, list[Path]] = {}
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith(".yaml"):
                    if "/" not in file_info.filename:
                        continue
                    filename = Path(file_info.filename.split("/")[-1])
                    if "." not in filename.stem:
                        continue
                    resource_type = filename.stem.rsplit(".", 1)[-1]
                    if attr_name := cls._FIELD_NAME_BY_RESOURCE_TYPE.get(resource_type.casefold()):
                        data.setdefault(attr_name, [])
                        context.setdefault(attr_name, [])
                        try:
                            loaded = yaml.safe_load(zip_ref.read(file_info).decode())
                        except Exception as e:
                            warnings.warn(
                                FileTypeUnexpectedWarning(filename, frozenset([".yaml", ".yml"]), str(e)), stacklevel=2
                            )
                            continue
                        if isinstance(loaded, list):
                            data[attr_name].extend(loaded)
                            context[attr_name].extend([filename] * len(loaded))
                        else:
                            data[attr_name].append(loaded)
                            context[attr_name].append(filename)
        return data, context

    def to_zip(self, zip_file: str | Path, exclude: set[str] | None = None) -> None:
        """Save the schema to a ZIP file as YAML files. This is compatible with the Cognite-Toolkit convention.

        Args:
            zip_file (str | Path): The ZIP file to save the schema to.
            exclude (set[str]): A set of attributes to exclude from the output.
        """
        exclude_set = exclude or set()
        with zipfile.ZipFile(zip_file, "w") as zip_ref:
            if "spaces" not in exclude_set:
                for space in self.spaces.values():
                    zip_ref.writestr(f"data_models/{space.space}.space.yaml", space.dump_yaml())
            if "data_models" not in exclude_set and self.data_model:
                zip_ref.writestr(
                    f"data_models/{self.data_model.external_id}.datamodel.yaml", self.data_model.dump_yaml()
                )
            if "views" not in exclude_set:
                for view in self.views.values():
                    zip_ref.writestr(f"data_models/views/{view.external_id}.view.yaml", view.dump_yaml())
            if "containers" not in exclude_set:
                for container in self.containers.values():
                    zip_ref.writestr(
                        f"data_models/containers/{container.external_id}.container.yaml", container.dump_yaml()
                    )
            if "node_types" not in exclude_set:
                for node in self.node_types.values():
                    zip_ref.writestr(f"data_models/nodes/{node.external_id}.node.yaml", node.dump_yaml())

    @classmethod
    def load(cls, data: str | dict[str, list[Any]], context: dict[str, list[Path]] | None = None) -> Self:
        """Loads a schema from a dictionary or a YAML or JSON formatted string.

        Args:
            data: The data to load the schema from. This can be a dictionary, a YAML or JSON formatted string.
            context: This provides linage for where the data was loaded from. This is used in Warnings
                if a single item fails to load.

        Returns:
            DMSSchema: The loaded schema.
        """
        context = context or {}
        if isinstance(data, str):
            # YAML is a superset of JSON, so we can use the same parser
            try:
                data_dict = yaml.safe_load(data)
            except Exception as e:
                raise NeatYamlError(str(e)) from None
            if not isinstance(data_dict, dict) and all(isinstance(v, list) for v in data_dict.values()):
                raise NeatYamlError(f"Invalid data structure: {type(data)}", "dict[str, list[Any]]") from None
        else:
            data_dict = data
        loaded: dict[str, Any] = {}
        for attr in fields(cls):
            if items := data_dict.get(attr.name) or data_dict.get(to_camel_case(attr.name)):
                if attr.name == "data_model":
                    if isinstance(items, list) and len(items) > 1:
                        try:
                            data_model_ids = [dm.DataModelId.load(item) for item in items]
                        except Exception as e:
                            data_model_file = context.get(attr.name, [Path("UNKNOWN")])[0]
                            warnings.warn(
                                FileTypeUnexpectedWarning(
                                    data_model_file, frozenset([dm.DataModelApply.__name__]), str(e)
                                ),
                                stacklevel=2,
                            )
                        else:
                            warnings.warn(
                                ResourcesDuplicatedWarning(
                                    frozenset(data_model_ids),
                                    "data model",
                                    "Will use the first DataModel.",
                                ),
                                stacklevel=2,
                            )
                    item = items[0] if isinstance(items, list) else items
                    try:
                        loaded[attr.name] = dm.DataModelApply.load(item)
                    except Exception as e:
                        data_model_file = context.get(attr.name, [Path("UNKNOWN")])[0]
                        warnings.warn(
                            FileTypeUnexpectedWarning(data_model_file, frozenset([dm.DataModelApply.__name__]), str(e)),
                            stacklevel=2,
                        )
                else:
                    try:
                        loaded[attr.name] = attr.type.load(items)  # type: ignore[union-attr]
                    except Exception as e:
                        loaded[attr.name] = cls._load_individual_resources(
                            items, attr, str(e), context.get(attr.name, [])
                        )
        return cls(**loaded)

    @classmethod
    def _load_individual_resources(
        cls: Any, items: list, attr: Field, trigger_error: str, resource_context: list[Path]
    ) -> list[Any]:
        type_ = cast(type, attr.type)
        resources = type_([])
        if not hasattr(type_, "_RESOURCE"):
            warnings.warn(
                FileTypeUnexpectedWarning(Path("UNKNOWN"), frozenset([type_.__name__]), trigger_error), stacklevel=2
            )
            return resources
        # Fallback to load individual resources.
        single_cls = type_._RESOURCE
        for no, item in enumerate(items):
            try:
                loaded_instance = single_cls.load(item)
            except Exception as e:
                try:
                    filepath = resource_context[no]
                except IndexError:
                    filepath = Path("UNKNOWN")
                # We use repr(e) instead of str(e) to include the exception type in the warning message
                warnings.warn(
                    FileTypeUnexpectedWarning(filepath, frozenset([single_cls.__name__]), repr(e)), stacklevel=2
                )
            else:
                resources.append(loaded_instance)
        return resources

    @classmethod
    def from_read_model(cls, model: dm.DataModel[dm.View]) -> Self:
        """Load schema from a read model.

        CAVEAT: This method infers the containers and spaces from the views. This means that
        for example indexes and constraints will not be captured in the containers.

        Args:
            model (dm.DataModel): The read model to load the schema from.
        """
        write_model = model.as_write()
        write_model.views = [view.as_id() for view in model.views or []]
        views = ViewApplyDict([view.as_write() for view in model.views])
        containers = ContainerApplyDict()
        for view in model.views:
            for prop in view.properties.values():
                if not isinstance(prop, dm.MappedProperty):
                    continue
                if prop.container not in containers:
                    containers[prop.container] = dm.ContainerApply(
                        space=prop.container.space,
                        external_id=prop.container.external_id,
                        properties={},
                        used_for=view.used_for,
                    )
                containers[prop.container].properties[prop.container_property_identifier] = dm.ContainerProperty(
                    type=prop.type,
                    nullable=prop.nullable,
                    auto_increment=prop.auto_increment,
                    immutable=prop.immutable,
                    default_value=prop.default_value,
                    name=prop.name,
                    description=prop.description,
                )

        schema = cls(data_model=write_model, views=views, containers=containers)
        schema.spaces = SpaceApplyDict(dm.SpaceApply(space) for space in schema.referenced_spaces())
        return schema

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
                key = to_camel_case(attr.name) if camel_case else attr.name
                if isinstance(items, CogniteResourceDict):
                    if sort:
                        output[key] = [
                            item.dump(camel_case) for item in sorted(items.values(), key=self._to_sortable_identifier)
                        ]
                    else:
                        output[key] = items.dump(camel_case)
                else:
                    output[key] = items.dump(camel_case=camel_case)
        return output

    @classmethod
    def _to_sortable_identifier(cls, item: Any) -> str | tuple[str, str] | tuple[str, str, str]:
        if isinstance(item, dm.ContainerApply | dm.ViewApply | dm.DataModelApply | dm.NodeApply):
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

    def referenced_spaces(self, include_indirect_references: bool = True) -> set[str]:
        """Get the spaces referenced by the schema.

        Args:
            include_indirect_references (bool): If True, the spaces referenced by as view.implements, and
                view.referenced_containers will be included in the output.
        Returns:
            set[str]: The spaces referenced by the schema.
        """
        referenced_spaces = {view.space for view in self.views.values()}
        referenced_spaces |= {container.space for container in self.containers.values()}
        if include_indirect_references:
            referenced_spaces |= {
                container.space for view in self.views.values() for container in view.referenced_containers()
            }
            referenced_spaces |= {parent.space for view in self.views.values() for parent in view.implements or []}
        referenced_spaces |= {node.space for node in self.node_types.values()}
        if self.data_model:
            referenced_spaces |= {self.data_model.space}
            referenced_spaces |= {view.space for view in self.data_model.views or []}
        referenced_spaces |= {s.space for s in self.spaces.values()}
        return referenced_spaces

    def referenced_container(self) -> set[dm.ContainerId]:
        referenced_containers = {
            container for view in self.views.values() for container in view.referenced_containers()
        }
        referenced_containers |= set(self.containers.keys())
        return referenced_containers

    def externally_referenced_containers(self) -> set[dm.ContainerId]:
        """Get the containers referenced by the schema that are not defined in the schema."""
        return {container for container in self.referenced_container() if container not in self.containers}

    def as_read_model(self) -> dm.DataModel[dm.View]:
        if self.data_model is None:
            raise ValueError("Data model is not defined")
        all_containers = self.containers.copy()
        all_views = self.views.copy()
        views: list[dm.View] = []
        for view in self.views.values():
            referenced_containers = ContainerApplyDict()
            properties: dict[str, ViewProperty] = {}
            # ChainMap is used to merge properties from the view and its parents
            # Note that the order of the ChainMap is important, as the first dictionary has the highest priority
            # So if a child and parent have the same property, the child property will be used.
            write_properties = ChainMap(view.properties, *(all_views[v].properties for v in view.implements or []))  # type: ignore[arg-type]
            for prop_name, prop in write_properties.items():
                read_prop = self._as_read_properties(prop, all_containers)
                if isinstance(read_prop, dm.MappedProperty) and read_prop.container not in referenced_containers:
                    referenced_containers[read_prop.container] = all_containers[read_prop.container]
                properties[prop_name] = read_prop

            read_view = dm.View(
                space=view.space,
                external_id=view.external_id,
                version=view.version,
                description=view.description,
                name=view.name,
                filter=view.filter,
                implements=view.implements.copy(),
                used_for=self._used_for(referenced_containers.values()),
                writable=self._writable(properties.values(), referenced_containers.values()),
                properties=properties,
                is_global=False,
                last_updated_time=0,
                created_time=0,
            )
            views.append(read_view)

        return dm.DataModel(
            space=self.data_model.space,
            external_id=self.data_model.external_id,
            version=self.data_model.version,
            name=self.data_model.name,
            description=self.data_model.description,
            views=views,
            is_global=False,
            last_updated_time=0,
            created_time=0,
        )

    @staticmethod
    def _as_read_properties(
        write: ViewPropertyApply, all_containers: MutableMapping[dm.ContainerId, dm.ContainerApply]
    ) -> ViewProperty:
        if isinstance(write, dm.MappedPropertyApply):
            container_prop = all_containers[write.container].properties[write.container_property_identifier]
            return dm.MappedProperty(
                container=write.container,
                container_property_identifier=write.container_property_identifier,
                name=write.name,
                description=write.description,
                source=write.source,
                type=container_prop.type,
                nullable=container_prop.nullable,
                auto_increment=container_prop.auto_increment,
                immutable=container_prop.immutable,
                # Likely bug in SDK.
                default_value=container_prop.default_value,  # type: ignore[arg-type]
            )
        if isinstance(write, dm.EdgeConnectionApply):
            edge_cls = SingleEdgeConnection if isinstance(write, SingleEdgeConnectionApply) else dm.MultiEdgeConnection
            return edge_cls(
                type=write.type,
                source=write.source,
                name=write.name,
                description=write.description,
                edge_source=write.edge_source,
                direction=write.direction,
            )
        if isinstance(write, ReverseDirectRelationApply):
            relation_cls = (
                SingleReverseDirectRelation
                if isinstance(write, SingleReverseDirectRelationApply)
                else dm.MultiReverseDirectRelation
            )
            return relation_cls(
                source=write.source,
                through=write.through,
                name=write.name,
                description=write.description,
            )
        raise ValueError(f"Cannot convert {write} to read format")

    @staticmethod
    def _used_for(containers: Iterable[dm.ContainerApply]) -> Literal["node", "edge", "all"]:
        used_for = {container.used_for for container in containers}
        if used_for == {"node"}:
            return "node"
        if used_for == {"edge"}:
            return "edge"
        return "all"

    @staticmethod
    def _writable(properties: Iterable[ViewProperty], containers: Iterable[dm.ContainerApply]) -> bool:
        used_properties = {
            (prop.container, prop.container_property_identifier)
            for prop in properties
            if isinstance(prop, dm.MappedProperty)
        }
        required_properties = {
            (container.as_id(), prop_id)
            for container in containers
            for prop_id, prop in container.properties.items()
            if not prop.nullable
        }
        # If a container has a required property that is not used by the view, the view is not writable
        return not bool(required_properties - used_properties)
