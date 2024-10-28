import json
import sys
import warnings
import zipfile
from collections import ChainMap, Counter, defaultdict
from collections.abc import Iterable, MutableMapping
from dataclasses import Field, dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar, Literal, cast

import yaml
from cognite.client import CogniteClient
from cognite.client import data_modeling as dm
from cognite.client.data_classes import DatabaseWrite, DatabaseWriteList, TransformationWrite, TransformationWriteList
from cognite.client.data_classes.data_modeling import ViewApply
from cognite.client.data_classes.data_modeling.views import (
    ReverseDirectRelation,
    ReverseDirectRelationApply,
    SingleEdgeConnection,
    SingleEdgeConnectionApply,
    SingleReverseDirectRelation,
    SingleReverseDirectRelationApply,
    ViewProperty,
    ViewPropertyApply,
)
from cognite.client.data_classes.transformations.common import Edges, EdgeType, Nodes, ViewInfo

from cognite.neat._issues import NeatError
from cognite.neat._issues.errors import (
    NeatYamlError,
    PropertyMappingDuplicatedError,
    PropertyNotFoundError,
    ResourceDuplicatedError,
    ResourceNotFoundError,
)
from cognite.neat._issues.warnings import (
    FileTypeUnexpectedWarning,
    ResourceNotFoundWarning,
    ResourceRetrievalWarning,
    ResourcesDuplicatedWarning,
)
from cognite.neat._issues.warnings.user_modeling import DirectRelationMissingSourceWarning
from cognite.neat._rules.models.data_types import _DATA_TYPE_BY_DMS_TYPE
from cognite.neat._utils.cdf.data_classes import (
    CogniteResourceDict,
    ContainerApplyDict,
    NodeApplyDict,
    RawTableWrite,
    RawTableWriteList,
    SpaceApplyDict,
    ViewApplyDict,
)
from cognite.neat._utils.cdf.loaders import ViewLoader
from cognite.neat._utils.rdf_ import get_inheritance_path
from cognite.neat._utils.text import to_camel

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
    # The last schema is the previous version of the data model. In the case, extension=addition, this
    # should not be modified.
    last: "DMSSchema | None" = None
    # Reference is typically the Enterprise model, while this is the solution model.
    reference: "DMSSchema | None" = None

    _FIELD_NAME_BY_RESOURCE_TYPE: ClassVar[dict[str, str]] = {
        "container": "containers",
        "view": "views",
        "datamodel": "data_model",
        "space": "spaces",
        "node": "node_types",
    }

    def _get_mapped_container_from_view(self, view_id: dm.ViewId) -> set[dm.ContainerId]:
        # index all views, including ones from reference
        view_by_id = self.views.copy()
        if self.reference:
            view_by_id.update(self.reference.views)

        if view_id not in view_by_id:
            raise ValueError(f"View {view_id} not found")

        indexed_implemented_views = {id_: view.implements for id_, view in view_by_id.items()}
        view_inheritance = get_inheritance_path(view_id, indexed_implemented_views)

        directly_referenced_containers = view_by_id[view_id].referenced_containers()
        inherited_referenced_containers = set()

        for parent_id in view_inheritance:
            if implemented_view := view_by_id.get(parent_id):
                inherited_referenced_containers |= implemented_view.referenced_containers()
            else:
                raise ResourceNotFoundError(parent_id, "view", view_id, "view")

        return directly_referenced_containers | inherited_referenced_containers

    @classmethod
    def from_model_id(cls, client: CogniteClient, data_model_id: dm.DataModelIdentifier) -> "DMSSchema":
        data_models = client.data_modeling.data_models.retrieve(data_model_id, inline_views=True)
        if len(data_models) == 0:
            raise ValueError(f"Data model {data_model_id} not found")
        data_model = data_models.latest_version()
        return cls.from_data_model(client, data_model)

    @classmethod
    def from_data_model(
        cls,
        client: CogniteClient,
        data_model: dm.DataModel[dm.View],
        reference_model: dm.DataModel[dm.View] | None = None,
    ) -> "DMSSchema":
        """Create a schema from a data model.

        If a reference model is provided, the schema will include a reference schema. To determine which views,
        and containers to put in the reference schema, the following rule is applied:

            If a view or container space is different from the data model space,
            it will be included in the reference schema.*

        *One exception to this rule is if a view is directly referenced by the data model. In this case, the view will
        be included in the data model schema, even if the space is different.

        Args:
            client: The Cognite client used for retrieving components referenced by the data model.
            data_model: The data model to create the schema from.
            reference_model: (Optional) The reference model to include in the schema.
                This is typically the Enterprise model.

        Returns:
            DMSSchema: The schema created from the data model.
        """
        views = dm.ViewList(data_model.views)

        data_model_write = data_model.as_write()
        data_model_write.views = list(views.as_ids())

        if reference_model:
            views.extend(reference_model.views)

        container_ids = views.referenced_containers()
        containers = client.data_modeling.containers.retrieve(list(container_ids))
        cls._append_referenced_containers(client, containers)

        space_ids = [data_model.space, reference_model.space] if reference_model else [data_model.space]
        space_read = client.data_modeling.spaces.retrieve(space_ids)
        if len(space_read) != len(space_ids):
            raise ValueError(f"Space(s) {space_read} not found")
        space_write = space_read.as_write()

        view_loader = ViewLoader(client)

        existing_view_ids = set(views.as_ids())

        # We need to include all views the edges/direct relations are pointing to have a complete schema.
        connection_referenced_view_ids: set[dm.ViewId] = set()
        for view in views:
            connection_referenced_view_ids |= cls._connection_references(view)
        connection_referenced_view_ids = connection_referenced_view_ids - existing_view_ids
        if connection_referenced_view_ids:
            for view_id in connection_referenced_view_ids:
                warnings.warn(
                    ResourceNotFoundWarning(view_id, "view", data_model_write.as_id(), "data model"),
                    stacklevel=2,
                )
            connection_referenced_views = view_loader.retrieve(list(connection_referenced_view_ids))
            if failed := connection_referenced_view_ids - set(connection_referenced_views.as_ids()):
                warnings.warn(ResourceRetrievalWarning(frozenset(failed), "view"), stacklevel=2)
            views.extend(connection_referenced_views)

        # We need to include parent views in the schema to make sure that the schema is valid.
        parent_view_ids = {parent for view in views for parent in view.implements or []}
        parents = view_loader.retrieve_all_parents(list(parent_view_ids - existing_view_ids))
        views.extend([parent for parent in parents if parent.as_id() not in existing_view_ids])

        # Converting views from read to write format requires to account for parents (implements)
        # as the read format contains all properties from all parents, while the write formate should not contain
        # properties from any parents.
        # The ViewLoader as_write method looks up parents and remove properties from them.
        view_write = ViewApplyDict([view_loader.as_write(view) for view in views])

        container_write = ContainerApplyDict(containers.as_write())
        user_space = data_model.space
        if reference_model:
            user_model_view_ids = set(data_model_write.views)
            ref_model_write = reference_model.as_write()
            ref_model_write.views = [view.as_id() for view in reference_model.views]

            ref_views = ViewApplyDict(
                [
                    view
                    for view_id, view in view_write.items()
                    if (view.space != user_space) or (view_id not in user_model_view_ids)
                ]
            )
            view_write = ViewApplyDict(
                [
                    view
                    for view_id, view in view_write.items()
                    if view.space == user_space or view_id in user_model_view_ids
                ]
            )

            ref_containers = ContainerApplyDict(
                [container for container in container_write.values() if container.space != user_space]
            )
            container_write = ContainerApplyDict(
                [container for container in container_write.values() if container.space == user_space]
            )

            ref_schema: DMSSchema | None = cls(
                spaces=SpaceApplyDict([s for s in space_write if s.space != user_space]),
                data_model=ref_model_write,
                views=ref_views,
                containers=ref_containers,
            )
        else:
            ref_schema = None
        return cls(
            spaces=SpaceApplyDict([s for s in space_write if s.space == user_space]),
            data_model=data_model_write,
            views=view_write,
            containers=container_write,
            reference=ref_schema,
        )

    @classmethod
    def _connection_references(cls, view: dm.View) -> set[dm.ViewId]:
        view_ids: set[dm.ViewId] = set()
        for prop in (view.properties or {}).values():
            if isinstance(prop, dm.MappedProperty) and isinstance(prop.type, dm.DirectRelation):
                if prop.source:
                    view_ids.add(prop.source)
            elif isinstance(prop, dm.EdgeConnection):
                view_ids.add(prop.source)
                if prop.edge_source:
                    view_ids.add(prop.edge_source)
            elif isinstance(prop, ReverseDirectRelation):
                view_ids.add(prop.source)
        return view_ids

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
                    if attr_name := cls._FIELD_NAME_BY_RESOURCE_TYPE.get(resource_type):
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
                        f"data_models/containers{container.external_id}.container.yaml", container.dump_yaml()
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
            if items := data_dict.get(attr.name) or data_dict.get(to_camel(attr.name)):
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
    def _load_individual_resources(cls, items: list, attr: Field, trigger_error: str, resource_context) -> list[Any]:
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
                key = to_camel(attr.name) if camel_case else attr.name
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

    def validate(self) -> list[NeatError]:
        errors: set[NeatError] = set()
        defined_spaces = self.spaces.copy()
        defined_containers = self.containers.copy()
        defined_views = self.views.copy()
        for other_schema in [self.reference, self.last]:
            if other_schema:
                defined_spaces |= other_schema.spaces
                defined_containers |= other_schema.containers
                defined_views |= other_schema.views

        for container in self.containers.values():
            if container.space not in defined_spaces:
                errors.add(
                    ResourceNotFoundError[str, dm.ContainerId](container.space, "space", container.as_id(), "container")
                )

        for view in self.views.values():
            view_id = view.as_id()
            if view.space not in defined_spaces:
                errors.add(ResourceNotFoundError(view.space, "space", view_id, "view"))

            for parent in view.implements or []:
                if parent not in defined_views:
                    errors.add(PropertyNotFoundError(parent, "view", "implements", view_id, "view"))

            for prop_name, prop in (view.properties or {}).items():
                if isinstance(prop, dm.MappedPropertyApply):
                    ref_container = defined_containers.get(prop.container)
                    if ref_container is None:
                        errors.add(ResourceNotFoundError(prop.container, "container", view_id, "view"))
                    elif prop.container_property_identifier not in ref_container.properties:
                        errors.add(
                            PropertyNotFoundError(
                                prop.container,
                                "container",
                                prop.container_property_identifier,
                                view_id,
                                "view",
                            )
                        )
                    else:
                        container_property = ref_container.properties[prop.container_property_identifier]

                        if isinstance(container_property.type, dm.DirectRelation) and prop.source is None:
                            warnings.warn(
                                DirectRelationMissingSourceWarning(view_id, prop_name),
                                stacklevel=2,
                            )

                if isinstance(prop, dm.EdgeConnectionApply) and prop.source not in defined_views:
                    errors.add(PropertyNotFoundError(prop.source, "view", prop_name, view_id, "view"))

                if (
                    isinstance(prop, dm.EdgeConnectionApply)
                    and prop.edge_source is not None
                    and prop.edge_source not in defined_views
                ):
                    errors.add(PropertyNotFoundError(prop.edge_source, "view", prop_name, view_id, "view"))

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
                        PropertyMappingDuplicatedError(
                            container_id,
                            "container",
                            container_property_identifier,
                            frozenset({dm.PropertyId(view_id, prop_name) for prop_name in view_properties}),
                            "view property",
                        )
                    )

        if self.data_model:
            model = self.data_model
            if model.space not in defined_spaces:
                errors.add(ResourceNotFoundError(model.space, "space", model.as_id(), "data model"))

            view_counts: dict[dm.ViewId, int] = defaultdict(int)
            for view_id_or_class in model.views or []:
                view_id = view_id_or_class if isinstance(view_id_or_class, dm.ViewId) else view_id_or_class.as_id()
                if view_id not in defined_views:
                    errors.add(ResourceNotFoundError(view_id, "view", model.as_id(), "data model"))
                view_counts[view_id] += 1

            for view_id, count in view_counts.items():
                if count > 1:
                    errors.add(
                        ResourceDuplicatedError(
                            view_id,
                            "view",
                            repr(model.as_id()),
                        )
                    )

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

    def as_read_model(self) -> dm.DataModel[dm.View]:
        if self.data_model is None:
            raise ValueError("Data model is not defined")
        all_containers = self.containers.copy()
        all_views = self.views.copy()
        for other_schema in [self.reference, self.last]:
            if other_schema:
                all_containers |= other_schema.containers
                all_views |= other_schema.views

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
    def _read_directory(cls, directory: Path) -> tuple[dict[str, list[Any]], dict[str, list[Path]]]:
        data, context = super()._read_directory(directory)
        for yaml_file in directory.rglob("*.yaml"):
            if yaml_file.parent.name in ("transformations", "raw"):
                attr_name = cls._FIELD_NAME_BY_RESOURCE_TYPE.get(yaml_file.parent.name, yaml_file.parent.name)
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
    def _read_zip(cls, zip_file: Path) -> tuple[dict[str, list[Any]], dict[str, list[Path]]]:
        data, context = super()._read_zip(zip_file)
        with zipfile.ZipFile(zip_file, "r") as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith(".yaml"):
                    if "/" not in file_info.filename:
                        continue
                    filepath = Path(file_info.filename)
                    if (parent := filepath.parent.name) in ("transformations", "raw"):
                        attr_name = cls._FIELD_NAME_BY_RESOURCE_TYPE.get(parent, parent)
                        data.setdefault(attr_name, [])
                        context.setdefault(attr_name, [])
                        try:
                            loaded = yaml.safe_load(zip_ref.read(file_info).decode())
                        except Exception as e:
                            warnings.warn(
                                FileTypeUnexpectedWarning(filepath, frozenset([".yaml", ".yml"]), str(e)), stacklevel=2
                            )
                            continue
                        if isinstance(loaded, list):
                            data[attr_name].extend(loaded)
                            context[attr_name].extend([filepath] * len(loaded))
                        else:
                            data[attr_name].append(loaded)
                            context[attr_name].append(filepath)
        return data, context

    @classmethod
    def from_dms(cls, schema: DMSSchema, instance_space: str | None = None) -> "PipelineSchema":
        if not schema.data_model:
            raise ValueError("PipelineSchema must contain at least one data model")
        first_data_model = schema.data_model
        # The database name is limited to 32 characters
        database_name = first_data_model.external_id[:32]
        instance_space = instance_space or first_data_model.space
        database = DatabaseWrite(name=database_name)
        parent_views = {parent for view in schema.views.values() for parent in view.implements or []}
        container_by_id = schema.containers.copy()

        transformations = TransformationWriteList([])
        raw_tables = RawTableWriteList([])
        for view in schema.views.values():
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
            data_model=schema.data_model,
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
