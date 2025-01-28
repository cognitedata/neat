import re
import warnings
from abc import ABC
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping
from datetime import date, datetime
from typing import ClassVar, Literal, TypeVar, cast, overload

from cognite.client.data_classes import data_modeling as dms
from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier, ViewId
from cognite.client.utils.useful_types import SequenceNotStr
from rdflib import Namespace

from cognite.neat._client import NeatClient
from cognite.neat._client.data_classes.data_modeling import ContainerApplyDict, ViewApplyDict
from cognite.neat._constants import (
    COGNITE_MODELS,
    COGNITE_SPACES,
    DMS_CONTAINER_PROPERTY_SIZE_LIMIT,
    DMS_RESERVED_PROPERTIES,
    get_default_prefixes_and_namespaces,
)
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._issues.warnings import NeatValueWarning
from cognite.neat._issues.warnings._models import (
    EnterpriseModelNotBuildOnTopOfCDMWarning,
    SolutionModelBuildOnTopOfCDMWarning,
)
from cognite.neat._rules._shared import (
    ReadInputRules,
    VerifiedRules,
)
from cognite.neat._rules.analysis import DMSAnalysis
from cognite.neat._rules.importers import DMSImporter
from cognite.neat._rules.models import (
    DMSInputRules,
    DMSRules,
    InformationRules,
    SheetList,
    data_types,
)
from cognite.neat._rules.models._rdfpath import Entity as RDFPathEntity
from cognite.neat._rules.models._rdfpath import RDFPath, SingleProperty
from cognite.neat._rules.models.data_types import AnyURI, DataType, Enum, File, String, Timeseries
from cognite.neat._rules.models.dms import DMSMetadata, DMSProperty, DMSValidation, DMSView
from cognite.neat._rules.models.dms._rules import DMSContainer, DMSEnum, DMSNode
from cognite.neat._rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    EdgeEntity,
    HasDataFilter,
    MultiValueTypeInfo,
    ReverseConnectionEntity,
    UnknownEntity,
    ViewEntity,
)
from cognite.neat._rules.models.information import InformationClass, InformationMetadata, InformationProperty
from cognite.neat._utils.text import to_camel

from ._base import T_VerifiedIn, T_VerifiedOut, VerifiedRulesTransformer
from ._verification import VerifyDMSRules

T_InputInRules = TypeVar("T_InputInRules", bound=ReadInputRules)
T_InputOutRules = TypeVar("T_InputOutRules", bound=ReadInputRules)


class ConversionTransformer(VerifiedRulesTransformer[T_VerifiedIn, T_VerifiedOut], ABC):
    """Base class for all conversion transformers."""

    ...


class ToCompliantEntities(VerifiedRulesTransformer[InformationRules, InformationRules]):  # type: ignore[misc]
    """Converts input rules to rules with compliant entity IDs that match regex patters used
    by DMS schema components."""

    @property
    def description(self) -> str:
        return "Ensures externalIDs are compliant with CDF"

    def transform(self, rules: InformationRules) -> InformationRules:
        copy = rules.model_copy(deep=True)
        copy.classes = self._fix_classes(copy.classes)
        copy.properties = self._fix_properties(copy.properties)
        return copy

    @classmethod
    def _fix_entity(cls, entity: str) -> str:
        entity = re.sub(r"[^_a-zA-Z0-9]+", "_", entity)

        # entity id must start with a letter
        if not entity[0].isalpha():
            entity = "prefix_" + entity
        # and end with a letter or number
        if not entity[-1].isalnum():
            entity = entity + "_suffix"

        # removing any double underscores that could occur
        return re.sub(r"[^a-zA-Z0-9]+", "_", entity)

    @classmethod
    def _fix_class(cls, class_: ClassEntity) -> ClassEntity:
        if isinstance(class_, ClassEntity) and type(class_.prefix) is str:
            class_ = ClassEntity(
                prefix=cls._fix_entity(class_.prefix),
                suffix=cls._fix_entity(class_.suffix),
            )

        return class_

    @classmethod
    def _fix_value_type(
        cls, value_type: DataType | ClassEntity | MultiValueTypeInfo
    ) -> DataType | ClassEntity | MultiValueTypeInfo:
        fixed_value_type: DataType | ClassEntity | MultiValueTypeInfo

        # value type specified as MultiValueTypeInfo
        if isinstance(value_type, MultiValueTypeInfo):
            fixed_value_type = MultiValueTypeInfo(
                types=[cast(DataType | ClassEntity, cls._fix_value_type(type_)) for type_ in value_type.types],
            )

        # value type specified as ClassEntity instance
        elif isinstance(value_type, ClassEntity):
            fixed_value_type = cls._fix_class(value_type)

        # this is a DataType instance but also we should default to original value
        else:
            fixed_value_type = value_type

        return fixed_value_type

    @classmethod
    def _fix_classes(cls, definitions: SheetList[InformationClass]) -> SheetList[InformationClass]:
        fixed_definitions = SheetList[InformationClass]()
        for definition in definitions:
            definition.class_ = cls._fix_class(definition.class_)
            fixed_definitions.append(definition)
        return fixed_definitions

    @classmethod
    def _fix_properties(cls, definitions: SheetList[InformationProperty]) -> SheetList[InformationProperty]:
        fixed_definitions = SheetList[InformationProperty]()
        for definition in definitions:
            definition.class_ = cls._fix_class(definition.class_)
            definition.property_ = cls._fix_entity(definition.property_)
            definition.value_type = cls._fix_value_type(definition.value_type)
            fixed_definitions.append(definition)
        return fixed_definitions


class PrefixEntities(ConversionTransformer):  # type: ignore[type-var]
    """Prefixes all entities with a given prefix if they are in the same space as data model."""

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    @property
    def description(self) -> str:
        return f"Prefixes all entities with {self._prefix!r} prefix if they are in the same space as data model."

    @overload
    def transform(self, rules: DMSRules) -> DMSRules: ...

    @overload
    def transform(self, rules: InformationRules) -> InformationRules: ...

    def transform(self, rules: InformationRules | DMSRules) -> InformationRules | DMSRules:
        copy: InformationRules | DMSRules = rules.model_copy(deep=True)

        # Case: Prefix Information Rules
        if isinstance(copy, InformationRules):
            # prefix classes
            for cls in copy.classes:
                if cls.class_.prefix == copy.metadata.prefix:
                    cls.class_ = self._with_prefix(cls.class_)

                if cls.implements:
                    # prefix parents
                    for i, parent_class in enumerate(cls.implements):
                        if parent_class.prefix == copy.metadata.prefix:
                            cls.implements[i] = self._with_prefix(parent_class)

            for prop in copy.properties:
                if prop.class_.prefix == copy.metadata.prefix:
                    prop.class_ = self._with_prefix(prop.class_)

                # value type property is not multi and it is ClassEntity

                if isinstance(prop.value_type, ClassEntity) and prop.value_type.prefix == copy.metadata.prefix:
                    prop.value_type = self._with_prefix(cast(ClassEntity, prop.value_type))
                elif isinstance(prop.value_type, MultiValueTypeInfo):
                    for i, value_type in enumerate(prop.value_type.types):
                        if isinstance(value_type, ClassEntity) and value_type.prefix == copy.metadata.prefix:
                            prop.value_type.types[i] = self._with_prefix(cast(ClassEntity, value_type))
            return copy

        # Case: Prefix DMS Rules
        elif isinstance(copy, DMSRules):
            for view in copy.views:
                if view.view.space == copy.metadata.space:
                    view.view = self._with_prefix(view.view)

                if view.implements:
                    for i, parent_view in enumerate(view.implements):
                        if parent_view.space == copy.metadata.space:
                            view.implements[i] = self._with_prefix(parent_view)

            for dms_prop in copy.properties:
                if dms_prop.view.space == copy.metadata.space:
                    dms_prop.view = self._with_prefix(dms_prop.view)

                if isinstance(dms_prop.value_type, ViewEntity) and dms_prop.value_type.space == copy.metadata.space:
                    dms_prop.value_type = self._with_prefix(dms_prop.value_type)

                if isinstance(dms_prop.container, ContainerEntity) and dms_prop.container.space == copy.metadata.space:
                    dms_prop.container = self._with_prefix(dms_prop.container)

            if copy.containers:
                for container in copy.containers:
                    if container.container.space == copy.metadata.space:
                        container.container = self._with_prefix(container.container)
            return copy

        raise NeatValueError(f"Unsupported rules type: {type(copy)}")

    @overload
    def _with_prefix(self, entity: ClassEntity) -> ClassEntity: ...

    @overload
    def _with_prefix(self, entity: ViewEntity) -> ViewEntity: ...

    @overload
    def _with_prefix(self, entity: ContainerEntity) -> ContainerEntity: ...

    def _with_prefix(
        self, entity: ViewEntity | ContainerEntity | ClassEntity
    ) -> ViewEntity | ContainerEntity | ClassEntity:
        if isinstance(entity, ViewEntity | ContainerEntity | ClassEntity):
            entity.suffix = f"{self._prefix}{entity.suffix}"

        else:
            raise NeatValueError(f"Unsupported entity type: {type(entity)}")

        return entity


class InformationToDMS(ConversionTransformer[InformationRules, DMSRules]):
    """Converts InformationRules to DMSRules."""

    def __init__(
        self, ignore_undefined_value_types: bool = False, reserved_properties: Literal["error", "warning"] = "error"
    ):
        self.ignore_undefined_value_types = ignore_undefined_value_types
        self.reserved_properties = reserved_properties

    def transform(self, rules: InformationRules) -> DMSRules:
        return _InformationRulesConverter(rules).as_dms_rules(
            self.ignore_undefined_value_types, self.reserved_properties
        )


class DMSToInformation(ConversionTransformer[DMSRules, InformationRules]):
    """Converts DMSRules to InformationRules."""

    def __init__(self, instance_namespace: Namespace | None = None):
        self.instance_namespace = instance_namespace

    def transform(self, rules: DMSRules) -> InformationRules:
        return _DMSRulesConverter(rules, self.instance_namespace).as_information_rules()


class ConvertToRules(ConversionTransformer[VerifiedRules, VerifiedRules]):
    """Converts any rules to any rules."""

    def __init__(self, out_cls: type[VerifiedRules]):
        self._out_cls = out_cls

    def transform(self, rules: VerifiedRules) -> VerifiedRules:
        if isinstance(rules, self._out_cls):
            return rules
        if isinstance(rules, InformationRules) and self._out_cls is DMSRules:
            return InformationToDMS().transform(rules)
        if isinstance(rules, DMSRules) and self._out_cls is InformationRules:
            return DMSToInformation().transform(rules)
        raise ValueError(f"Unsupported conversion from {type(rules)} to {self._out_cls}")


_T_Entity = TypeVar("_T_Entity", bound=ClassEntity | ViewEntity)


class SetIDDMSModel(VerifiedRulesTransformer[DMSRules, DMSRules]):
    def __init__(self, new_id: DataModelId | tuple[str, str, str]):
        self.new_id = DataModelId.load(new_id)

    @property
    def description(self) -> str:
        return f"Sets the Data Model ID to {self.new_id.as_tuple()}"

    def transform(self, rules: DMSRules) -> DMSRules:
        if self.new_id.version is None:
            raise NeatValueError("Version is required when setting a new Data Model ID")
        dump = rules.dump()
        dump["metadata"]["space"] = self.new_id.space
        dump["metadata"]["external_id"] = self.new_id.external_id
        dump["metadata"]["version"] = self.new_id.version
        # Serialize and deserialize to set the new space and external_id
        # as the default values for the new model.
        return DMSRules.model_validate(DMSInputRules.load(dump).dump())


class ToExtensionModel(VerifiedRulesTransformer[DMSRules, DMSRules], ABC):
    type_: ClassVar[str]

    def __init__(self, new_model_id: DataModelIdentifier) -> None:
        self.new_model_id = DataModelId.load(new_model_id)
        if not self.new_model_id.version:
            raise NeatValueError("Version is required for the new model.")

    @property
    def description(self) -> str:
        return f"Create new data model {self.new_model_id} of type {self.type_.replace('_', ' ')} data model."


class ToEnterpriseModel(ToExtensionModel):
    type_: ClassVar[str] = "enterprise"

    def __init__(
        self,
        new_model_id: DataModelIdentifier,
        org_name: str = "My",
        dummy_property: str = "GUID",
        move_connections: bool = False,
    ):
        super().__init__(new_model_id)
        self.dummy_property = dummy_property
        self.org_name = org_name
        self.move_connections = move_connections

    def transform(self, rules: DMSRules) -> DMSRules:
        reference_model_id = rules.metadata.as_data_model_id()
        if reference_model_id not in COGNITE_MODELS:
            warnings.warn(
                EnterpriseModelNotBuildOnTopOfCDMWarning(reference_model_id=reference_model_id).as_message(),
                stacklevel=2,
            )

        return self._to_enterprise(rules)

    def _to_enterprise(self, reference_model: DMSRules) -> DMSRules:
        enterprise_model = reference_model.model_copy(deep=True)

        enterprise_model.metadata.name = f"{self.org_name} {self.type_} data model"
        enterprise_model.metadata.space = self.new_model_id.space
        enterprise_model.metadata.external_id = self.new_model_id.external_id
        enterprise_model.metadata.version = cast(str, self.new_model_id.version)

        # Here we are creating enterprise views with a single container with a dummy property
        # for each view
        enterprise_views, enterprise_containers, enterprise_properties = self._create_new_views(enterprise_model)

        # We keep the reference views, and adding new enterprise views...
        enterprise_model.views.extend(enterprise_views)

        if self.move_connections:
            # Move connections from reference model to new enterprise model
            enterprise_properties.extend(self._create_connection_properties(enterprise_model, enterprise_views))

        # ... however, we do not want to keep the reference containers and properties
        # these we are getting for free through the implements.
        enterprise_model.containers = enterprise_containers
        enterprise_model.properties = enterprise_properties

        return enterprise_model

    @staticmethod
    def _create_connection_properties(rules: DMSRules, new_views: SheetList[DMSView]) -> SheetList[DMSProperty]:
        """Creates a new connection property for each connection property in the reference model.

        This is for example when you create an enterprise model from CogniteCore, you ensure that your
        new Asset, Equipment, TimeSeries, Activity, and File views all point to each other.
        """
        # Note all new news have an implements attribute that points to the original view
        previous_by_new_view = {view.implements[0]: view.view for view in new_views if view.implements}
        connection_properties = SheetList[DMSProperty]()
        for prop in rules.properties:
            if (
                isinstance(prop.value_type, ViewEntity)
                and prop.view in previous_by_new_view
                and prop.value_type in previous_by_new_view
            ):
                new_property = prop.model_copy(deep=True)
                new_property.view = previous_by_new_view[prop.view]
                new_property.value_type = previous_by_new_view[prop.value_type]
                connection_properties.append(new_property)

        return connection_properties

    def _create_new_views(
        self, rules: DMSRules
    ) -> tuple[SheetList[DMSView], SheetList[DMSContainer], SheetList[DMSProperty]]:
        """Creates new views for the new model.

        If the dummy property is provided, it will also create a new container for each view
        with a single property that is the dummy property.
        """
        new_views = SheetList[DMSView]()
        new_containers = SheetList[DMSContainer]()
        new_properties = SheetList[DMSProperty]()

        for definition in rules.views:
            view_entity = self._remove_cognite_affix(definition.view)
            view_entity.version = cast(str, self.new_model_id.version)
            view_entity.prefix = self.new_model_id.space
            new_views.append(
                DMSView(
                    view=view_entity,
                    implements=[definition.view],
                    in_model=True,
                    name=definition.name,
                )
            )

            if self.dummy_property is None:
                continue

            container_entity = ContainerEntity(space=view_entity.prefix, externalId=view_entity.external_id)

            container = DMSContainer(container=container_entity)

            property_id = f"{to_camel(view_entity.suffix)}{self.dummy_property}"
            property_ = DMSProperty(
                view=view_entity,
                view_property=property_id,
                value_type=String(),
                nullable=True,
                immutable=False,
                is_list=False,
                container=container_entity,
                container_property=property_id,
            )

            new_properties.append(property_)
            new_containers.append(container)

        return new_views, new_containers, new_properties

    def _remove_cognite_affix(self, entity: ViewEntity) -> ViewEntity:
        """This method removes `Cognite` affix from the entity."""
        new_suffix = entity.suffix.replace("Cognite", self.org_name)
        return ViewEntity(space=entity.space, externalId=new_suffix, version=entity.version)


class ToSolutionModel(ToExtensionModel):
    """Creates a solution data model based on an existing data model.

    The solution data model will create a new view for each view in the existing model.

    Args:
        new_model_id: DataData model identifier for the new model.
        dummy_property: Only applicable if mode='write'. The identifier of the dummy property in the newly created
            container.
        exclude_views_in_other_spaces: Whether to exclude views that are not in the same space as the existing model,
            when creating the solution model.

    """

    type_: ClassVar[str] = "solution"

    def __init__(
        self,
        new_model_id: DataModelIdentifier,
        properties: Literal["repeat", "connection"] = "connection",
        dummy_property: str | None = "GUID",
        direct_property: str = "enterprise",
        view_prefix: str = "Enterprise",
        filter_type: Literal["container", "view"] = "container",
        exclude_views_in_other_spaces: bool = False,
        skip_cognite_views: bool = True,
    ):
        super().__init__(new_model_id)
        self.properties = properties
        self.dummy_property = dummy_property
        self.direct_property = direct_property
        self.view_prefix = view_prefix
        self.filter_type = filter_type
        self.exclude_views_in_other_spaces = exclude_views_in_other_spaces
        self.skip_cognite_views = skip_cognite_views

    def transform(self, rules: DMSRules) -> DMSRules:
        reference_model = rules
        reference_model_id = reference_model.metadata.as_data_model_id()
        if reference_model_id in COGNITE_MODELS:
            warnings.warn(
                SolutionModelBuildOnTopOfCDMWarning(reference_model_id=reference_model_id),
                stacklevel=2,
            )
        return self._to_solution(reference_model)

    def _to_solution(self, reference_rules: DMSRules) -> DMSRules:
        """For creation of solution data model / rules specifically for mapping over existing containers."""
        reference_rules = self._expand_properties(reference_rules.model_copy(deep=True))

        new_views, new_properties, read_view_by_new_view = self._create_views(reference_rules)
        new_containers, new_container_properties = self._create_containers_update_view_filter(
            new_views, reference_rules, read_view_by_new_view
        )
        new_properties.extend(new_container_properties)

        if self.properties == "connection":
            # Ensure the Enterprise view and the new solution view are next to each other
            new_properties.sort(
                key=lambda prop: (
                    prop.view.external_id.removeprefix(self.view_prefix),
                    bool(prop.view.external_id.startswith(self.view_prefix)),
                )
            )
        else:
            new_properties.sort(key=lambda prop: (prop.view.external_id, prop.view_property))

        metadata = reference_rules.metadata.model_copy(
            deep=True,
            update={
                "space": self.new_model_id.space,
                "external_id": self.new_model_id.external_id,
                "version": self.new_model_id.version,
                "name": f"{self.type_} data model",
            },
        )
        return DMSRules(
            metadata=metadata,
            properties=new_properties,
            views=new_views,
            containers=new_containers or None,
            enum=reference_rules.enum,
            nodes=reference_rules.nodes,
        )

    @staticmethod
    def _expand_properties(rules: DMSRules) -> DMSRules:
        probe = DMSAnalysis(rules)
        ancestor_properties_by_view = probe.classes_with_properties(
            consider_inheritance=True, allow_different_namespace=True
        )
        property_ids_by_view = {
            view: {prop.view_property for prop in properties}
            for view, properties in probe.classes_with_properties(consider_inheritance=False).items()
        }
        for view, property_ids in property_ids_by_view.items():
            ancestor_properties = ancestor_properties_by_view.get(view, [])
            for prop in ancestor_properties:
                if isinstance(prop.connection, ReverseConnectionEntity):
                    # If you try to add a reverse direct relation of a parent, it will fail as the ValueType of the
                    # original property will point to the parent view, and not the child.
                    continue
                if prop.view_property not in property_ids:
                    rules.properties.append(prop)
                    property_ids.add(prop.view_property)
        return rules

    def _create_views(
        self, reference: DMSRules
    ) -> tuple[SheetList[DMSView], SheetList[DMSProperty], dict[ViewEntity, ViewEntity]]:
        renaming: dict[ViewEntity, ViewEntity] = {}
        new_views = SheetList[DMSView]()
        read_view_by_new_view: dict[ViewEntity, ViewEntity] = {}
        skipped_views: set[ViewEntity] = set()
        for ref_view in reference.views:
            if (self.skip_cognite_views and ref_view.view.space in COGNITE_SPACES) or (
                self.exclude_views_in_other_spaces and ref_view.view.space != reference.metadata.space
            ):
                skipped_views.add(ref_view.view)
                continue
            new_entity = ViewEntity(
                # MyPy we validate that version is string in the constructor
                space=self.new_model_id.space,
                externalId=ref_view.view.external_id,
                version=self.new_model_id.version,  # type: ignore[arg-type]
            )
            if self.properties == "connection":
                # Set suffix to existing view and introduce a new view.
                # This will be used to point to the one view in the Enterprise model,
                # while the new view will to be written to.
                new_entity.suffix = f"{self.view_prefix}{ref_view.view.suffix}"
                new_view = DMSView(
                    view=ViewEntity(
                        # MyPy we validate that version is string in the constructor
                        space=self.new_model_id.space,
                        externalId=ref_view.view.external_id,
                        version=self.new_model_id.version,  # type: ignore[arg-type]
                    )
                )
                new_views.append(new_view)
                read_view_by_new_view[new_view.view] = new_entity
            elif self.properties == "repeat":
                # This is a slight misuse of the read_view_by_new_view. For the repeat mode, we only
                # care about the keys in this dictionary. But instead of creating a separate set, we
                # do this.
                read_view_by_new_view[new_entity] = new_entity

            renaming[ref_view.view] = new_entity
            new_views.append(ref_view.model_copy(deep=True, update={"implements": None, "view": new_entity}))

        new_properties = SheetList[DMSProperty]()
        for prop in reference.properties:
            if prop.view in skipped_views:
                continue
            new_property = prop.model_copy(deep=True)
            if new_property.value_type in renaming and isinstance(new_property.value_type, ViewEntity):
                new_property.value_type = renaming[new_property.value_type]
            if new_property.view in renaming:
                new_property.view = renaming[new_property.view]
            new_properties.append(new_property)
        return new_views, new_properties, read_view_by_new_view

    def _create_containers_update_view_filter(
        self, new_views: SheetList[DMSView], reference: DMSRules, read_view_by_new_view: dict[ViewEntity, ViewEntity]
    ) -> tuple[SheetList[DMSContainer], SheetList[DMSProperty]]:
        new_containers = SheetList[DMSContainer]()
        container_properties: SheetList[DMSProperty] = SheetList[DMSProperty]()
        ref_containers_by_ref_view: dict[ViewEntity, set[ContainerEntity]] = defaultdict(set)
        ref_views_by_external_id = {
            view.view.external_id: view for view in reference.views if view.view.space == reference.metadata.space
        }
        if self.filter_type == "container":
            for prop in reference.properties:
                if prop.container:
                    ref_containers_by_ref_view[prop.view].add(prop.container)
        read_views = set(read_view_by_new_view.values())
        for view in new_views:
            if view.view in read_view_by_new_view:
                read_view = read_view_by_new_view[view.view]
                container_entity = ContainerEntity(space=self.new_model_id.space, externalId=view.view.external_id)
                prefix = to_camel(view.view.suffix)
                if self.properties == "repeat" and self.dummy_property:
                    property_ = DMSProperty(
                        view=view.view,
                        view_property=f"{prefix}{self.dummy_property}",
                        value_type=String(),
                        nullable=True,
                        immutable=False,
                        is_list=False,
                        container=container_entity,
                        container_property=f"{prefix}{self.dummy_property}",
                    )
                    new_containers.append(DMSContainer(container=container_entity))
                    container_properties.append(property_)
                elif self.properties == "repeat" and self.dummy_property is None:
                    # For this case we set the filter. This is used by the DataProductModel.
                    # Inherit view filter from original model to ensure the same instances are returned
                    # when querying the new view.
                    if ref_view := ref_views_by_external_id.get(view.view.external_id):
                        self._set_view_filter(view, ref_containers_by_ref_view, ref_view)
                elif self.properties == "connection" and self.direct_property:
                    property_ = DMSProperty(
                        view=view.view,
                        view_property=self.direct_property,
                        value_type=read_view,
                        nullable=True,
                        immutable=False,
                        is_list=False,
                        container=container_entity,
                        container_property=self.direct_property,
                    )
                    new_containers.append(DMSContainer(container=container_entity))
                    container_properties.append(property_)
                else:
                    raise NeatValueError(f"Unsupported properties mode: {self.properties}")

            if self.properties == "connection" and view.view in read_views:
                # Need to ensure that the 'Enterprise' view always returns the same instances
                # as the original view, no matter which properties are removed by the user.
                if ref_view := ref_views_by_external_id.get(view.view.external_id.removeprefix(self.view_prefix)):
                    self._set_view_filter(view, ref_containers_by_ref_view, ref_view)
        return new_containers, container_properties

    def _set_view_filter(
        self, view: DMSView, ref_containers_by_ref_view: dict[ViewEntity, set[ContainerEntity]], ref_view: DMSView
    ) -> None:
        if self.filter_type == "view":
            view.filter_ = HasDataFilter(inner=[ref_view.view])
        elif self.filter_type == "container" and (ref_containers := ref_containers_by_ref_view.get(ref_view.view)):
            # Sorting to ensure deterministic order
            view.filter_ = HasDataFilter(inner=sorted(ref_containers))


class ToDataProductModel(ToSolutionModel):
    """

    Args:
        new_model_id: DataData model identifier for the new model.
        include: The views to include in the data product data model. Can be either "same-space" or "all".
        filter_type: This is the type of filter to apply to the new views. The filter is used to
            ensure that the new views will return the same instance as the original views. The view filter is the
            simplest filter, but it has limitation in the fusion UI. The container filter is in essence a more
            verbose version of the view filter, and it has better support in the fusion UI. The default is "container".
    """

    type_: ClassVar[str] = "data_product"

    def __init__(
        self,
        new_model_id: DataModelIdentifier,
        include: Literal["same-space", "all"] = "same-space",
        filter_type: Literal["container", "view"] = "container",
        skip_cognite_views: bool = True,
    ):
        super().__init__(
            new_model_id,
            properties="repeat",
            dummy_property=None,
            filter_type=filter_type,
            exclude_views_in_other_spaces=include == "same-space",
            skip_cognite_views=skip_cognite_views,
        )
        self.include = include

    def transform(self, rules: DMSRules) -> DMSRules:
        # Overwrite this to avoid the warning.
        return self._to_solution(rules)


class DropModelViews(VerifiedRulesTransformer[DMSRules, DMSRules]):
    _ASSET_VIEW = ViewId("cdf_cdm", "CogniteAsset", "v1")
    _VIEW_BY_COLLECTION: Mapping[Literal["3D", "Annotation", "BaseViews"], frozenset[ViewId]] = {
        "3D": frozenset(
            {
                ViewId("cdf_cdm", "Cognite3DModel", "v1"),
                ViewId("cdf_cdm", "Cognite3DObject", "v1"),
                ViewId("cdf_cdm", "Cognite3DRevision", "v1"),
                ViewId("cdf_cdm", "Cognite3DTransformation", "v1"),
                ViewId("cdf_cdm", "Cognite360Image", "v1"),
                ViewId("cdf_cdm", "Cognite360ImageAnnotation", "v1"),
                ViewId("cdf_cdm", "Cognite360ImageCollection", "v1"),
                ViewId("cdf_cdm", "Cognite360ImageModel", "v1"),
                ViewId("cdf_cdm", "Cognite360ImageStation", "v1"),
                ViewId("cdf_cdm", "CogniteCADModel", "v1"),
                ViewId("cdf_cdm", "CogniteCADNode", "v1"),
                ViewId("cdf_cdm", "CogniteCADRevision", "v1"),
                ViewId("cdf_cdm", "CogniteCubeMap", "v1"),
                ViewId("cdf_cdm", "CognitePointCloudModel", "v1"),
                ViewId("cdf_cdm", "CognitePointCloudRevision", "v1"),
                ViewId("cdf_cdm", "CognitePointCloudVolume", "v1"),
            }
        ),
        "Annotation": frozenset(
            {
                ViewId("cdf_cdm", "CogniteAnnotation", "v1"),
                ViewId("cdf_cdm", "CogniteDiagramAnnotation", "v1"),
            }
        ),
        "BaseViews": frozenset(
            {
                ViewId("cdf_cdm", "CogniteDescribable", "v1"),
                ViewId("cdf_cdm", "CogniteSchedulable", "v1"),
                ViewId("cdf_cdm", "CogniteSourceable", "v1"),
                ViewId("cdf_cdm", "CogniteVisualizable", "v1"),
            }
        ),
    }

    def __init__(
        self,
        view_external_id: str | SequenceNotStr[str] | None = None,
        group: Literal["3D", "Annotation", "BaseViews"]
        | Collection[Literal["3D", "Annotation", "BaseViews"]]
        | None = None,
    ):
        self.drop_external_ids = (
            {view_external_id} if isinstance(view_external_id, str) else set(view_external_id or [])
        )
        self.drop_collection = (
            [group]
            if isinstance(group, str)
            else cast(
                list[Literal["3D", "Annotation", "BaseViews"]],
                [collection for collection in group or [] if collection in self._VIEW_BY_COLLECTION],
            )
        )

    def transform(self, rules: DMSRules) -> DMSRules:
        exclude_views: set[ViewEntity] = {
            view.view for view in rules.views if view.view.suffix in self.drop_external_ids
        }
        if rules.metadata.as_data_model_id() in COGNITE_MODELS:
            exclude_views |= {
                ViewEntity.from_id(view_id, "v1")
                for collection in self.drop_collection
                for view_id in self._VIEW_BY_COLLECTION[collection]
            }
        new_model = rules.model_copy(deep=True)

        properties_by_view = DMSAnalysis(new_model).classes_with_properties(consider_inheritance=True)

        new_model.views = SheetList[DMSView]([view for view in new_model.views if view.view not in exclude_views])
        new_properties = SheetList[DMSProperty]()
        mapped_containers: set[ContainerEntity] = set()
        for view in new_model.views:
            for prop in properties_by_view[view.view]:
                if "3D" in self.drop_collection and self._is_asset_3D_property(prop):
                    # We filter out the 3D property of asset
                    continue
                if isinstance(prop.value_type, ViewEntity) and prop.value_type in exclude_views:
                    continue
                new_properties.append(prop)
                if prop.container:
                    mapped_containers.add(prop.container)

        new_model.properties = new_properties
        new_model.containers = (
            SheetList[DMSContainer](
                [container for container in new_model.containers or [] if container.container in mapped_containers]
            )
            or None
        )

        return new_model

    @classmethod
    def _is_asset_3D_property(cls, prop: DMSProperty) -> bool:
        return prop.view.as_id() == cls._ASSET_VIEW and prop.view_property == "object3D"

    @property
    def description(self) -> str:
        return f"Removed {len(self.drop_external_ids) + len(self.drop_collection)} views from data model"


class IncludeReferenced(VerifiedRulesTransformer[DMSRules, DMSRules]):
    def __init__(self, client: NeatClient, include_properties: bool = False) -> None:
        self._client = client
        self.include_properties = include_properties

    def transform(self, rules: DMSRules) -> DMSRules:
        dms_rules = rules
        view_ids, container_ids = DMSValidation(dms_rules).imported_views_and_containers_ids()
        if not (view_ids or container_ids):
            warnings.warn(
                NeatValueWarning(
                    f"Data model {dms_rules.metadata.as_data_model_id()} does not have any "
                    "referenced views or containers."
                    "that is not already included in the data model."
                ),
                stacklevel=2,
            )
            return dms_rules

        schema = self._client.schema.retrieve([v.as_id() for v in view_ids], [c.as_id() for c in container_ids])
        copy_ = dms_rules.model_copy(deep=True)
        # Sorting to ensure deterministic order
        schema.containers = ContainerApplyDict(sorted(schema.containers.items(), key=lambda x: x[0].as_tuple()))
        schema.views = ViewApplyDict(sorted(schema.views.items(), key=lambda x: x[0].as_tuple()))
        importer = DMSImporter(schema)

        imported = importer.to_rules()
        if imported.rules is None:
            raise NeatValueError("Could not import the referenced views and containers.")

        verified = VerifyDMSRules(validate=False).transform(imported)
        if copy_.containers is None:
            copy_.containers = verified.containers
        else:
            existing_containers = {c.container for c in copy_.containers}
            copy_.containers.extend([c for c in verified.containers or [] if c.container not in existing_containers])
        existing_views = {v.view for v in copy_.views}
        copy_.views.extend([v for v in verified.views if v.view not in existing_views])
        if self.include_properties:
            existing_properties = {(p.view, p.view_property) for p in copy_.properties}
            copy_.properties.extend(
                [p for p in verified.properties if (p.view, p.view_property) not in existing_properties]
            )

        return copy_

    @property
    def description(self) -> str:
        return "Included referenced views and containers in the data model."


class AddClassImplements(VerifiedRulesTransformer[InformationRules, InformationRules]):
    def __init__(self, implements: str, suffix: str):
        self.implements = implements
        self.suffix = suffix

    def transform(self, rules: InformationRules) -> InformationRules:
        info_rules = rules
        output = info_rules.model_copy(deep=True)
        for class_ in output.classes:
            if class_.class_.suffix.endswith(self.suffix):
                class_.implements = [ClassEntity(prefix=class_.class_.prefix, suffix=self.implements)]
        return output

    @property
    def description(self) -> str:
        return f"Added implements property to classes with suffix {self.suffix}"


class ClassicPrepareCore(VerifiedRulesTransformer[InformationRules, InformationRules]):
    """Update the classic data model with the following:

    This is a special purpose transformer that is only intended to be used with when reading
    from classic cdf using the neat.read.cdf.classic.graph(...).

    - ClassicTimeseries.isString from boolean to string
    - Add class ClassicSourceSystem, and update all source properties from string to ClassicSourceSystem.
    - Rename externalId properties to classicExternalId
    - Renames the Relationship.sourceExternalId and Relationship.targetExternalId to startNode and endNode
    - If reference_timeseries is True, the classicExternalId property of the TimeSeries class will change type
      from string to timeseries.
    - If reference_files is True, the classicExternalId property of the File class will change type from string to file.
    """

    def __init__(
        self,
        instance_namespace: Namespace,
        reference_timeseries: bool = False,
        reference_files: bool = False,
    ) -> None:
        self.instance_namespace = instance_namespace
        self.reference_timeseries = reference_timeseries
        self.reference_files = reference_files

    @property
    def description(self) -> str:
        return "Update the classic data model to the data types in Cognite Core."

    def transform(self, rules: InformationRules) -> InformationRules:
        output = rules.model_copy(deep=True)
        for prop in output.properties:
            if prop.class_.suffix == "Timeseries" and prop.property_ == "isString":
                prop.value_type = String()
        prefix = output.metadata.prefix
        namespace = output.metadata.namespace
        source_system_class = InformationClass(
            class_=ClassEntity(prefix=prefix, suffix="ClassicSourceSystem"),
            description="A source system that provides data to the data model.",
            neatId=namespace["ClassicSourceSystem"],
        )
        output.classes.append(source_system_class)
        for prop in output.properties:
            if prop.property_ == "source" and prop.class_.suffix != "ClassicSourceSystem":
                prop.value_type = ClassEntity(prefix=prefix, suffix="ClassicSourceSystem")
            elif prop.property_ == "externalId":
                prop.property_ = "classicExternalId"
                if self.reference_timeseries and prop.class_.suffix == "ClassicTimeSeries":
                    prop.value_type = Timeseries()
                elif self.reference_files and prop.class_.suffix == "ClassicFile":
                    prop.value_type = File()
            elif prop.property_ == "sourceExternalId" and prop.class_.suffix == "ClassicRelationship":
                prop.property_ = "startNode"
            elif prop.property_ == "targetExternalId" and prop.class_.suffix == "ClassicRelationship":
                prop.property_ = "endNode"
        instance_prefix = next(
            (prefix for prefix, namespace in output.prefixes.items() if namespace == self.instance_namespace), None
        )
        if instance_prefix is None:
            raise NeatValueError("Instance namespace not found in the prefixes.")

        output.properties.append(
            InformationProperty(
                neatId=namespace["ClassicSourceSystem/name"],
                property_="name",
                value_type=String(),
                class_=ClassEntity(prefix=prefix, suffix="ClassicSourceSystem"),
                max_count=1,
                instance_source=RDFPath(
                    traversal=SingleProperty(
                        class_=RDFPathEntity(
                            prefix=instance_prefix,
                            suffix="ClassicSourceSystem",
                        ),
                        property=RDFPathEntity(prefix=instance_prefix, suffix="name"),
                    ),
                ),
            )
        )
        return output


class ChangeViewPrefix(VerifiedRulesTransformer[DMSRules, DMSRules]):
    def __init__(self, old: str, new: str) -> None:
        self.old = old
        self.new = new

    def transform(self, rules: DMSRules) -> DMSRules:
        output = rules.model_copy(deep=True)
        new_by_old: dict[ViewEntity, ViewEntity] = {}
        for view in output.views:
            if view.view.external_id.startswith(self.old):
                new_external_id = f"{self.new}{view.view.external_id.removeprefix(self.old)}"
                new_view_entity = view.view.copy(update={"suffix": new_external_id})
                new_by_old[view.view] = new_view_entity
                view.view = new_view_entity
        for view in output.views:
            if view.implements:
                view.implements = [new_by_old.get(implemented, implemented) for implemented in view.implements]
        for prop in output.properties:
            if prop.view in new_by_old:
                prop.view = new_by_old[prop.view]
            if prop.value_type in new_by_old and isinstance(prop.value_type, ViewEntity):
                prop.value_type = new_by_old[prop.value_type]
        return output


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
            if isinstance(prop.value_type, Enum) and prop.value_type.collection not in existing_enum_collections:
                if output.enum is None:
                    output.enum = SheetList[DMSEnum]()
                output.enum.append(new_enum_collections_by_entity[prop.value_type.collection])

        existing_nodes = {node.node for node in output.nodes or []}
        for node in self.extra.nodes or []:
            if node.node not in existing_nodes:
                if output.nodes is None:
                    output.nodes = SheetList[DMSNode]()
                output.nodes.append(node)

        return output

    @property
    def description(self) -> str:
        return f"Merged with {self.extra.metadata.as_data_model_id()}"


class MergeInformationRules(VerifiedRulesTransformer[InformationRules, InformationRules]):
    def __init__(self, extra: InformationRules) -> None:
        self.extra = extra

    def transform(self, rules: InformationRules) -> InformationRules:
        output = rules.model_copy(deep=True)
        existing_classes = {cls.class_ for cls in output.classes}
        for cls in self.extra.classes:
            if cls.class_ not in existing_classes:
                output.classes.append(cls)
        existing_properties = {(prop.class_, prop.property_) for prop in output.properties}
        for prop in self.extra.properties:
            if (prop.class_, prop.property_) not in existing_properties:
                output.properties.append(prop)
        for prefix, namespace in self.extra.prefixes.items():
            if prefix not in output.prefixes:
                output.prefixes[prefix] = namespace
        return output


class _InformationRulesConverter:
    _start_or_end_node: ClassVar[frozenset[str]] = frozenset({"endNode", "end_node", "startNode", "start_node"})

    def __init__(self, information: InformationRules):
        self.rules = information
        self.property_count_by_container: dict[ContainerEntity, int] = defaultdict(int)

    def as_dms_rules(
        self, ignore_undefined_value_types: bool = False, reserved_properties: Literal["error", "warning"] = "error"
    ) -> "DMSRules":
        from cognite.neat._rules.models.dms._rules import (
            DMSContainer,
            DMSProperty,
            DMSRules,
            DMSView,
        )

        info_metadata = self.rules.metadata
        default_version = info_metadata.version
        default_space = self._to_space(info_metadata.prefix)
        dms_metadata = self._convert_metadata_to_dms(info_metadata)

        properties_by_class: dict[ClassEntity, set[str]] = defaultdict(set)
        for prop in self.rules.properties:
            properties_by_class[prop.class_].add(prop.property_)

        # Edge Classes is defined by having both startNode and endNode properties
        edge_classes = {
            cls_
            for cls_, class_properties in properties_by_class.items()
            if ({"startNode", "start_node"} & class_properties) and ({"endNode", "end_node"} & class_properties)
        }
        edge_value_types_by_class_property_pair = {
            (prop.class_, prop.property_): prop.value_type
            for prop in self.rules.properties
            if prop.value_type in edge_classes and isinstance(prop.value_type, ClassEntity)
        }
        end_node_by_edge = {
            prop.class_: prop.value_type
            for prop in self.rules.properties
            if prop.class_ in edge_classes
            and (prop.property_ == "endNode" or prop.property_ == "end_node")
            and isinstance(prop.value_type, ClassEntity)
        }

        properties_by_class: dict[ClassEntity, list[DMSProperty]] = defaultdict(list)
        referenced_containers: dict[ContainerEntity, Counter[ClassEntity]] = defaultdict(Counter)
        for prop in self.rules.properties:
            if ignore_undefined_value_types and isinstance(prop.value_type, UnknownEntity):
                continue
            if prop.class_ in edge_classes and prop.property_ in self._start_or_end_node:
                continue
            if prop.property_ in DMS_RESERVED_PROPERTIES:
                msg = f"Property {prop.property_} is a reserved property in DMS."
                if reserved_properties == "error":
                    raise NeatValueError(msg)
                warnings.warn(NeatValueWarning(f"{msg} Skipping..."), stacklevel=2)
                continue

            dms_property = self._as_dms_property(
                prop,
                default_space,
                default_version,
                edge_classes,
                edge_value_types_by_class_property_pair,
                end_node_by_edge,
            )
            properties_by_class[prop.class_].append(dms_property)
            if dms_property.container:
                referenced_containers[dms_property.container][prop.class_] += 1

        views: list[DMSView] = []

        for cls_ in self.rules.classes:
            dms_view = DMSView(
                name=cls_.name,
                view=cls_.class_.as_view_entity(default_space, default_version),
                description=cls_.description,
                implements=self._get_view_implements(cls_, info_metadata),
            )

            dms_view.logical = cls_.neatId
            views.append(dms_view)

        class_by_entity = {cls_.class_: cls_ for cls_ in self.rules.classes}

        existing_containers: set[ContainerEntity] = set()

        containers: list[DMSContainer] = []
        for container_entity, class_entities in referenced_containers.items():
            if container_entity in existing_containers:
                continue
            constrains = self._create_container_constraint(
                class_entities, default_space, class_by_entity, referenced_containers
            )
            most_used_class_entity = class_entities.most_common(1)[0][0]
            class_ = class_by_entity[most_used_class_entity]

            if len(set(class_entities) - set(edge_classes)) == 0:
                used_for: Literal["node", "edge", "all"] = "edge"
            elif len(set(class_entities) - set(edge_classes)) == len(class_entities):
                used_for = "node"
            else:
                used_for = "all"

            container = DMSContainer(
                container=container_entity,
                name=class_.name,
                description=class_.description,
                constraint=constrains or None,
                used_for=used_for,
            )
            containers.append(container)

        dms_rules = DMSRules(
            metadata=dms_metadata,
            properties=SheetList[DMSProperty]([prop for prop_set in properties_by_class.values() for prop in prop_set]),
            views=SheetList[DMSView](views),
            containers=SheetList[DMSContainer](containers),
        )

        self.rules.sync_with_dms_rules(dms_rules)

        return dms_rules

    @staticmethod
    def _create_container_constraint(
        class_entities: Counter[ClassEntity],
        default_space: str,
        class_by_entity: dict[ClassEntity, InformationClass],
        referenced_containers: Collection[ContainerEntity],
    ) -> list[ContainerEntity]:
        constrains: list[ContainerEntity] = []
        for entity in class_entities:
            class_ = class_by_entity[entity]
            for parent in class_.implements or []:
                parent_entity = parent.as_container_entity(default_space)
                if parent_entity in referenced_containers:
                    constrains.append(parent_entity)
        return constrains

    @classmethod
    def _convert_metadata_to_dms(cls, metadata: InformationMetadata) -> "DMSMetadata":
        from cognite.neat._rules.models.dms._rules import (
            DMSMetadata,
        )

        dms_metadata = DMSMetadata(
            space=metadata.space,
            version=metadata.version,
            external_id=metadata.external_id,
            creator=metadata.creator,
            name=metadata.name,
            created=metadata.created,
            updated=metadata.updated,
        )

        dms_metadata.logical = metadata.identifier
        return dms_metadata

    def _as_dms_property(
        self,
        info_property: InformationProperty,
        default_space: str,
        default_version: str,
        edge_classes: set[ClassEntity],
        edge_value_types_by_class_property_pair: dict[tuple[ClassEntity, str], ClassEntity],
        end_node_by_edge: dict[ClassEntity, ClassEntity],
    ) -> "DMSProperty":
        from cognite.neat._rules.models.dms._rules import DMSProperty

        # returns property type, which can be ObjectProperty or DatatypeProperty
        value_type = self._get_value_type(
            info_property,
            default_space,
            default_version,
            edge_classes,
            end_node_by_edge,
        )

        connection = self._get_connection(
            info_property, value_type, edge_value_types_by_class_property_pair, default_space, default_version
        )

        container: ContainerEntity | None = None
        container_property: str | None = None
        is_list: bool | None = info_property.is_list
        nullable: bool | None = not info_property.is_mandatory
        if isinstance(connection, EdgeEntity):
            nullable = None
        elif connection == "direct":
            nullable = True
            container, container_property = self._get_container(info_property, default_space)
        else:
            container, container_property = self._get_container(info_property, default_space)

        dms_property = DMSProperty(
            name=info_property.name,
            value_type=value_type,
            nullable=nullable,
            is_list=is_list,
            connection=connection,
            default=info_property.default,
            container=container,
            container_property=container_property,
            view=info_property.class_.as_view_entity(default_space, default_version),
            view_property=info_property.property_,
        )

        # linking
        dms_property.logical = info_property.neatId

        return dms_property

    @staticmethod
    def _get_connection(
        prop: InformationProperty,
        value_type: DataType | ViewEntity | DMSUnknownEntity,
        edge_value_types_by_class_property_pair: dict[tuple[ClassEntity, str], ClassEntity],
        default_space: str,
        default_version: str,
    ) -> Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None:
        if (
            isinstance(value_type, ViewEntity)
            and (prop.class_, prop.property_) in edge_value_types_by_class_property_pair
        ):
            edge_value_type = edge_value_types_by_class_property_pair[(prop.class_, prop.property_)]
            return EdgeEntity(properties=edge_value_type.as_view_entity(default_space, default_version))
        if isinstance(value_type, ViewEntity) and prop.is_list:
            return EdgeEntity()
        elif isinstance(value_type, ViewEntity):
            return "direct"
        # defaulting to direct connection
        elif isinstance(value_type, DMSUnknownEntity):
            return "direct"
        return None

    def _get_value_type(
        self,
        prop: InformationProperty,
        default_space: str,
        default_version: str,
        edge_classes: set[ClassEntity],
        end_node_by_edge: dict[ClassEntity, ClassEntity],
    ) -> DataType | ViewEntity | DMSUnknownEntity:
        if isinstance(prop.value_type, DataType):
            return prop.value_type

        # UnknownEntity should  resolve to DMSUnknownEntity
        # meaning end node type is unknown
        elif isinstance(prop.value_type, UnknownEntity):
            return DMSUnknownEntity()

        elif isinstance(prop.value_type, ClassEntity) and (prop.value_type in edge_classes):
            if prop.value_type in end_node_by_edge:
                return end_node_by_edge[prop.value_type].as_view_entity(default_space, default_version)
            # This occurs if the end node is not pointing to a class
            warnings.warn(
                NeatValueWarning(
                    f"Edge class {prop.value_type} does not have 'endNode' property, defaulting to DMSUnknownEntity"
                ),
                stacklevel=2,
            )
            return DMSUnknownEntity()
        elif isinstance(prop.value_type, ClassEntity):
            return prop.value_type.as_view_entity(default_space, default_version)

        elif isinstance(prop.value_type, MultiValueTypeInfo):
            # Multi Object type should resolve to DMSUnknownEntity
            # meaning end node type is unknown
            if prop.value_type.is_multi_object_type():
                non_unknown = [type_ for type_ in prop.value_type.types if isinstance(type_, UnknownEntity)]
                if list(non_unknown) == 1:
                    #
                    return non_unknown[0].as_view_entity(default_space, default_version)
                return DMSUnknownEntity()

            # Multi Data type should resolve to a single data type, or it should
            elif prop.value_type.is_multi_data_type():
                return self.convert_multi_data_type(prop.value_type)

            # Mixed types default to string
            else:
                non_any_uri = [type_ for type_ in prop.value_type.types if type_ != AnyURI()]
                if list(non_any_uri) == 1:
                    if isinstance(non_any_uri[0], ClassEntity):
                        return non_any_uri[0].as_view_entity(default_space, default_version)
                    else:
                        return non_any_uri[0]
                return String()

        raise ValueError(f"Unsupported value type: {prop.value_type.type_}")

    @classmethod
    def _to_space(cls, prefix: str) -> str:
        """Ensures that the prefix comply with the CDF space regex"""
        prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", prefix)
        if prefix[0].isdigit() or prefix[0] == "_":
            prefix = f"a{prefix}"
        prefix = prefix[:43]
        if prefix[-1] == "_":
            prefix = f"{prefix[:-1]}1"
        return prefix

    def _get_container(self, prop: InformationProperty, default_space: str) -> tuple[ContainerEntity, str]:
        container_entity = prop.class_.as_container_entity(default_space)

        while self.property_count_by_container[container_entity] >= DMS_CONTAINER_PROPERTY_SIZE_LIMIT:
            container_entity.suffix = self._bump_suffix(container_entity.suffix)

        self.property_count_by_container[container_entity] += 1
        return container_entity, prop.property_

    def _get_view_implements(self, cls_: InformationClass, metadata: InformationMetadata) -> list[ViewEntity]:
        implements = []
        for parent in cls_.implements or []:
            view_entity = parent.as_view_entity(metadata.prefix, metadata.version)
            implements.append(view_entity)
        return implements

    @staticmethod
    def _bump_suffix(suffix: str) -> str:
        suffix_number = re.search(r"\d+$", suffix)

        if suffix_number:
            return suffix[: suffix_number.start()] + str(int(suffix_number.group()) + 1)
        else:
            return f"{suffix}2"

    @staticmethod
    def convert_multi_data_type(value_type: MultiValueTypeInfo) -> DataType:
        if not value_type.is_multi_data_type():
            raise ValueError("Only MultiValueType with DataType types is supported")
        # We check above that there are no ClassEntity types in the MultiValueType
        py_types = {type_.python for type_ in value_type.types}  # type: ignore[union-attr]

        # JSON mixed with other types should resolve to string that is safe choice
        if dms.Json in py_types and len(py_types) > 1:
            return data_types.String()
        elif dms.Json in py_types:
            return data_types.Json()
        elif not (py_types - {bool}):
            return data_types.Boolean()
        elif not (py_types - {int, bool}):
            return data_types.Integer()
        elif not (py_types - {float, int, bool}):
            return data_types.Double()
        elif not (py_types - {datetime, date}):
            return data_types.DateTime()

        return data_types.String()


class _DMSRulesConverter:
    def __init__(self, dms: DMSRules, instance_namespace: Namespace | None = None) -> None:
        self.dms = dms
        self.instance_namespace = instance_namespace

    def as_information_rules(
        self,
    ) -> "InformationRules":
        from cognite.neat._rules.models.information._rules import (
            InformationClass,
            InformationProperty,
            InformationRules,
        )

        dms = self.dms.metadata

        metadata = self._convert_metadata_to_info(dms)

        classes: list[InformationClass] = []
        for view in self.dms.views:
            info_class = InformationClass(
                # we do not want a version in class as we use URI for the class
                class_=ClassEntity(prefix=view.view.prefix, suffix=view.view.suffix),
                description=view.description,
                implements=[
                    # we do not want a version in class as we use URI for the class
                    implemented_view.as_class(skip_version=True)
                    for implemented_view in view.implements or []
                ],
            )

            # Linking
            info_class.physical = view.neatId
            classes.append(info_class)

        prefixes = get_default_prefixes_and_namespaces()
        instance_prefix: str | None = None
        if self.instance_namespace:
            instance_prefix = next((k for k, v in prefixes.items() if v == self.instance_namespace), None)
            if instance_prefix is None:
                # We need to add a new prefix
                instance_prefix = f"prefix_{len(prefixes) + 1}"
                prefixes[instance_prefix] = self.instance_namespace

        properties: list[InformationProperty] = []
        value_type: DataType | ClassEntity | str
        for property_ in self.dms.properties:
            if isinstance(property_.value_type, DataType):
                value_type = property_.value_type
            elif isinstance(property_.value_type, ViewEntity):
                value_type = ClassEntity(
                    prefix=property_.value_type.prefix,
                    suffix=property_.value_type.suffix,
                )
            elif isinstance(property_.value_type, DMSUnknownEntity):
                value_type = UnknownEntity()
            else:
                raise ValueError(f"Unsupported value type: {property_.value_type.type_}")

            transformation: RDFPath | None = None
            if instance_prefix is not None:
                transformation = RDFPath(
                    traversal=SingleProperty(
                        class_=RDFPathEntity(prefix=instance_prefix, suffix=property_.view.external_id),
                        property=RDFPathEntity(prefix=instance_prefix, suffix=property_.view_property),
                    )
                )

            info_property = InformationProperty(
                # Removing version
                class_=ClassEntity(suffix=property_.view.suffix, prefix=property_.view.prefix),
                property_=property_.view_property,
                value_type=value_type,
                description=property_.description,
                min_count=(0 if property_.nullable or property_.nullable is None else 1),
                max_count=(float("inf") if property_.is_list or property_.nullable is None else 1),
                instance_source=transformation,
            )

            # Linking
            info_property.physical = property_.neatId

            properties.append(info_property)

        info_rules = InformationRules(
            metadata=metadata,
            properties=SheetList[InformationProperty](properties),
            classes=SheetList[InformationClass](classes),
            prefixes=prefixes,
        )

        self.dms.sync_with_info_rules(info_rules)

        return info_rules

    @classmethod
    def _convert_metadata_to_info(cls, metadata: DMSMetadata) -> "InformationMetadata":
        from cognite.neat._rules.models.information._rules import InformationMetadata

        return InformationMetadata(
            space=metadata.space,
            external_id=metadata.external_id,
            version=metadata.version,
            description=metadata.description,
            name=metadata.name,
            creator=metadata.creator,
            created=metadata.created,
            updated=metadata.updated,
        )
