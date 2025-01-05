import dataclasses
import re
import warnings
from abc import ABC
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping
from datetime import date, datetime
from typing import ClassVar, Literal, TypeVar, cast, overload

from cognite.client.data_classes import data_modeling as dms
from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier, ViewId

from cognite.neat._client import NeatClient
from cognite.neat._client.data_classes.data_modeling import ContainerApplyDict, ViewApplyDict
from cognite.neat._constants import (
    COGNITE_MODELS,
    DMS_CONTAINER_PROPERTY_SIZE_LIMIT,
)
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._issues.warnings import NeatValueWarning
from cognite.neat._issues.warnings._models import (
    EnterpriseModelNotBuildOnTopOfCDMWarning,
    SolutionModelBuildOnTopOfCDMWarning,
)
from cognite.neat._rules._shared import (
    ReadInputRules,
    ReadRules,
    T_InputRules,
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
from cognite.neat._rules.models.data_types import AnyURI, DataType, String
from cognite.neat._rules.models.dms import DMSMetadata, DMSProperty, DMSValidation, DMSView
from cognite.neat._rules.models.dms._rules import DMSContainer
from cognite.neat._rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    EdgeEntity,
    Entity,
    HasDataFilter,
    MultiValueTypeInfo,
    ReverseConnectionEntity,
    T_Entity,
    UnknownEntity,
    ViewEntity,
)
from cognite.neat._rules.models.information import InformationClass, InformationMetadata, InformationProperty
from cognite.neat._rules.models.information._rules_input import (
    InformationInputClass,
    InformationInputProperty,
    InformationInputRules,
)
from cognite.neat._utils.text import to_camel

from ._base import RulesTransformer
from ._verification import VerifyDMSRules

T_VerifiedInRules = TypeVar("T_VerifiedInRules", bound=VerifiedRules)
T_VerifiedOutRules = TypeVar("T_VerifiedOutRules", bound=VerifiedRules)
T_InputInRules = TypeVar("T_InputInRules", bound=ReadInputRules)
T_InputOutRules = TypeVar("T_InputOutRules", bound=ReadInputRules)


class ConversionTransformer(RulesTransformer[T_VerifiedInRules, T_VerifiedOutRules], ABC):
    """Base class for all conversion transformers."""

    ...


class ToCompliantEntities(RulesTransformer[ReadRules[InformationInputRules], ReadRules[InformationInputRules]]):  # type: ignore[misc]
    """Converts input rules to rules with compliant entity IDs that match regex patters used
    by DMS schema components."""

    @property
    def description(self) -> str:
        return "Ensures externalIDs are compliant with CDF"

    def transform(self, rules: ReadRules[InformationInputRules]) -> ReadRules[InformationInputRules]:
        if rules.rules is None:
            return rules
        copy: InformationInputRules = dataclasses.replace(rules.rules)
        copy.classes = self._fix_classes(copy.classes)
        copy.properties = self._fix_properties(copy.properties)
        return ReadRules(copy, rules.read_context)

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
    def _fix_class(cls, class_: str | ClassEntity) -> str | ClassEntity:
        if isinstance(class_, str):
            if len(class_.split(":")) == 2:
                prefix, suffix = class_.split(":")
                class_ = f"{cls._fix_entity(prefix)}:{cls._fix_entity(suffix)}"

            else:
                class_ = cls._fix_entity(class_)

        elif isinstance(class_, ClassEntity) and type(class_.prefix) is str:
            class_ = ClassEntity(
                prefix=cls._fix_entity(class_.prefix),
                suffix=cls._fix_entity(class_.suffix),
            )

        return class_

    @classmethod
    def _fix_value_type(
        cls, value_type: str | DataType | ClassEntity | MultiValueTypeInfo
    ) -> str | DataType | ClassEntity | MultiValueTypeInfo:
        fixed_value_type: str | DataType | ClassEntity | MultiValueTypeInfo

        if isinstance(value_type, str):
            # this is a multi value type but as string
            if " | " in value_type:
                value_types = value_type.split(" | ")
                fixed_value_type = " | ".join([cast(str, cls._fix_value_type(v)) for v in value_types])
            # this is value type specified with prefix:suffix string
            elif ":" in value_type:
                fixed_value_type = cls._fix_class(value_type)

            # this is value type specified as suffix only
            else:
                fixed_value_type = cls._fix_entity(value_type)

        # value type specified as instances of DataType, ClassEntity or MultiValueTypeInfo
        elif isinstance(value_type, MultiValueTypeInfo):
            fixed_value_type = MultiValueTypeInfo(
                types=[cast(DataType | ClassEntity, cls._fix_value_type(type_)) for type_ in value_type.types],
            )
        elif isinstance(value_type, ClassEntity):
            fixed_value_type = cls._fix_class(value_type)

        # this is a DataType instance but also we should default to original value
        else:
            fixed_value_type = value_type

        return fixed_value_type

    @classmethod
    def _fix_classes(cls, definitions: list[InformationInputClass]) -> list[InformationInputClass]:
        fixed_definitions = []
        for definition in definitions:
            definition.class_ = cls._fix_class(definition.class_)
            fixed_definitions.append(definition)
        return fixed_definitions

    @classmethod
    def _fix_properties(cls, definitions: list[InformationInputProperty]) -> list[InformationInputProperty]:
        fixed_definitions = []
        for definition in definitions:
            definition.class_ = cls._fix_class(definition.class_)
            definition.property_ = cls._fix_entity(definition.property_)
            definition.value_type = cls._fix_value_type(definition.value_type)
            fixed_definitions.append(definition)
        return fixed_definitions


class PrefixEntities(RulesTransformer[ReadRules[T_InputRules], ReadRules[T_InputRules]]):  # type: ignore[type-var]
    """Prefixes all entities with a given prefix."""

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix

    @property
    def description(self) -> str:
        return f"Prefixes all views with {self._prefix!r}"

    def transform(self, rules: ReadRules[T_InputRules]) -> ReadRules[T_InputRules]:
        in_ = rules.rules
        if in_ is None:
            return rules
        copy: T_InputRules = dataclasses.replace(in_)
        if isinstance(copy, InformationInputRules):
            prefixed_by_class: dict[str, str] = {}
            for cls in copy.classes:
                prefixed = str(self._with_prefix(cls.class_))
                prefixed_by_class[str(cls.class_)] = prefixed
                cls.class_ = prefixed
            for prop in copy.properties:
                prop.class_ = self._with_prefix(prop.class_)
                if str(prop.value_type) in prefixed_by_class:
                    prop.value_type = prefixed_by_class[str(prop.value_type)]
            return ReadRules(copy, rules.read_context)  # type: ignore[arg-type]
        elif isinstance(copy, DMSInputRules):
            prefixed_by_view: dict[str, str] = {}
            for view in copy.views:
                prefixed = str(self._with_prefix(view.view))
                prefixed_by_view[str(view.view)] = prefixed
                view.view = prefixed
            for dms_prop in copy.properties:
                dms_prop.view = self._with_prefix(dms_prop.view)
                if str(dms_prop.value_type) in prefixed_by_view:
                    dms_prop.value_type = prefixed_by_view[str(dms_prop.value_type)]
            if copy.containers:
                for container in copy.containers:
                    container.container = self._with_prefix(container.container)
            return ReadRules(copy, rules.read_context)
        raise NeatValueError(f"Unsupported rules type: {type(copy)}")

    @overload
    def _with_prefix(self, raw: str) -> str: ...

    @overload
    def _with_prefix(self, raw: T_Entity) -> T_Entity: ...

    def _with_prefix(self, raw: str | T_Entity) -> str | T_Entity:
        is_entity_format = not isinstance(raw, str)
        entity = Entity.load(raw)
        output: ClassEntity | ViewEntity | ContainerEntity
        if isinstance(entity, ClassEntity):
            output = ClassEntity(prefix=entity.prefix, suffix=f"{self._prefix}{entity.suffix}", version=entity.version)
        elif isinstance(entity, ViewEntity):
            output = ViewEntity(
                space=entity.space, externalId=f"{self._prefix}{entity.external_id}", version=entity.version
            )
        elif isinstance(entity, ContainerEntity):
            output = ContainerEntity(space=entity.space, externalId=f"{self._prefix}{entity.external_id}")
        elif isinstance(entity, UnknownEntity | Entity):
            return f"{self._prefix}{raw}"
        else:
            raise NeatValueError(f"Unsupported entity type: {type(entity)}")
        if is_entity_format:
            return cast(T_Entity, output)
        return str(output)


class InformationToDMS(ConversionTransformer[InformationRules, DMSRules]):
    """Converts InformationRules to DMSRules."""

    def __init__(self, ignore_undefined_value_types: bool = False, mode: Literal["edge_properties"] | None = None):
        self.ignore_undefined_value_types = ignore_undefined_value_types
        self.mode = mode

    def transform(self, rules: InformationRules) -> DMSRules:
        return _InformationRulesConverter(rules).as_dms_rules(self.ignore_undefined_value_types, self.mode)


class DMSToInformation(ConversionTransformer[DMSRules, InformationRules]):
    """Converts DMSRules to InformationRules."""

    def transform(self, rules: DMSRules) -> InformationRules:
        return _DMSRulesConverter(rules).as_information_rules()


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


class SetIDDMSModel(RulesTransformer[DMSRules, DMSRules]):
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


class ToExtensionModel(RulesTransformer[DMSRules, DMSRules], ABC):
    type_: ClassVar[str]

    def __init__(self, new_model_id: DataModelIdentifier, org_name: str, dummy_property: str | None = None) -> None:
        self.new_model_id = DataModelId.load(new_model_id)
        if not self.new_model_id.version:
            raise NeatValueError("Version is required for the new model.")
        self.org_name = org_name
        self.dummy_property = dummy_property

    @property
    def description(self) -> str:
        return f"Prepared data model {self.new_model_id} to be {self.type_.replace('_', ' ')} data model."

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

            prefix = to_camel(view_entity.suffix)
            property_ = DMSProperty(
                view=view_entity,
                view_property=f"{prefix}{self.dummy_property}",
                value_type=String(),
                nullable=True,
                immutable=False,
                is_list=False,
                container=container_entity,
                container_property=f"{prefix}{self.dummy_property}",
            )

            new_properties.append(property_)
            new_containers.append(container)

        return new_views, new_containers, new_properties

    def _remove_cognite_affix(self, entity: _T_Entity) -> _T_Entity:
        """This method removes `Cognite` affix from the entity."""
        new_suffix = entity.suffix.replace("Cognite", self.org_name or "")
        if isinstance(entity, ViewEntity):
            return ViewEntity(space=entity.space, externalId=new_suffix, version=entity.version)  # type: ignore[return-value]
        elif isinstance(entity, ClassEntity):
            return ClassEntity(prefix=entity.prefix, suffix=new_suffix, version=entity.version)  # type: ignore[return-value]
        raise ValueError(f"Unsupported entity type: {type(entity)}")


class ToEnterpriseModel(ToExtensionModel):
    type_: ClassVar[str] = "enterprise"

    def __init__(
        self,
        new_model_id: DataModelIdentifier,
        org_name: str = "My",
        dummy_property: str = "GUID",
        move_connections: bool = False,
    ):
        super().__init__(new_model_id, org_name, dummy_property)
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
        dump = reference_model.dump()

        # This will create reference model components in the enterprise model space
        enterprise_model = DMSRules.model_validate(DMSInputRules.load(dump).dump())

        # Post validation metadata update:
        enterprise_model.metadata.name = self.type_
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
            enterprise_properties.extend(self._move_connections(enterprise_model))

        # ... however, we do not want to keep the reference containers and properties
        enterprise_model.containers = enterprise_containers
        enterprise_model.properties = enterprise_properties

        return enterprise_model

    @staticmethod
    def _move_connections(rules: DMSRules) -> SheetList[DMSProperty]:
        implements: dict[ViewEntity, list[ViewEntity]] = defaultdict(list)
        new_properties = SheetList[DMSProperty]()

        for view in rules.views:
            if view.view.space == rules.metadata.space and view.implements:
                for implemented_view in view.implements:
                    implements.setdefault(implemented_view, []).append(view.view)

        # currently only supporting single implementation of reference view in enterprise view
        # connections that do not have properties
        if all(len(v) == 1 for v in implements.values()):
            for prop_ in rules.properties:
                if (
                    prop_.view.space != rules.metadata.space
                    and prop_.connection
                    and isinstance(prop_.value_type, ViewEntity)
                    and implements.get(prop_.view)
                    and implements.get(prop_.value_type)
                ):
                    if isinstance(prop_.connection, EdgeEntity) and prop_.connection.properties:
                        continue
                    new_property = prop_.model_copy(deep=True)
                    new_property.view = implements[prop_.view][0]
                    new_property.value_type = implements[prop_.value_type][0]
                    new_properties.append(new_property)

        return new_properties


class ToSolutionModel(ToExtensionModel):
    """Creates a solution data model based on an existing data model.

    The solution data model will create a new view for each view in the existing model.

    Args:
        new_model_id: DataData model identifier for the new model.
        org_name: If the existing model is a Cognite Data Model, this will replace the "Cognite" affix.
        mode: The mode of the solution model. Either "read" or "write". A "write" model will create a new
            container for each view with a dummy property. Read mode will only inherit the view filter from the
            original model.
        dummy_property: Only applicable if mode='write'. The identifier of the dummy property in the newly created
            container.
        exclude_views_in_other_spaces: Whether to exclude views that are not in the same space as the existing model,
            when creating the solution model.
        filter_type: If mode="read", this is the type of filter to apply to the new views. The filter is used to
            ensure that the new views will return the same instance as the original views. The view filter is the
            simplest filter, but it has limitation in the fusion UI. The container filter is in essence a more
            verbose version of the view filter, and it has better support in the fusion UI. The default is "container".

    """

    type_: ClassVar[str] = "solution"

    def __init__(
        self,
        new_model_id: DataModelIdentifier,
        org_name: str = "My",
        mode: Literal["read", "write"] = "read",
        dummy_property: str | None = "GUID",
        exclude_views_in_other_spaces: bool = True,
        filter_type: Literal["container", "view"] = "container",
    ):
        super().__init__(new_model_id, org_name, dummy_property if mode == "write" else None)
        self.mode = mode
        self.exclude_views_in_other_spaces = exclude_views_in_other_spaces
        self.filter_type = filter_type

    def transform(self, rules: DMSRules) -> DMSRules:
        reference_model = rules
        reference_model_id = reference_model.metadata.as_data_model_id()

        # if model is solution then we need to get correct space for views and containers
        if self.mode not in ["read", "write"]:
            raise NeatValueError(f"Unsupported mode: {self.mode}")

        if reference_model_id in COGNITE_MODELS:
            warnings.warn(
                SolutionModelBuildOnTopOfCDMWarning(reference_model_id=reference_model_id),
                stacklevel=2,
            )

        return self._to_solution(reference_model)

    @staticmethod
    def _has_views_in_multiple_space(rules: DMSRules) -> bool:
        return any(view.view.space != rules.metadata.space for view in rules.views)

    def _to_solution(self, reference_rules: DMSRules) -> DMSRules:
        """For creation of solution data model / rules specifically for mapping over existing containers."""

        dump = reference_rules.dump(entities_exclude_defaults=True)

        # Prepare new model metadata prior validation
        # Since we dropped the defaults, all entities will update the space and version
        # to the new model space and version
        dump["metadata"]["name"] = f"{self.org_name} {self.type_} data model"
        dump["metadata"]["space"] = self.new_model_id.space
        dump["metadata"]["external_id"] = self.new_model_id.external_id
        dump["metadata"]["version"] = self.new_model_id.version

        solution_model = DMSRules.model_validate(DMSInputRules.load(dump).dump())

        # This is not desirable for the containers, so we manually fix that here.
        # It is easier to change the space for all entities and then revert the containers, than
        # to change the space for all entities except the containers.
        for prop in solution_model.properties:
            if prop.container and prop.container.space == self.new_model_id.space:
                # If the container is in the new model space, we want to map it to the reference model space
                # This is reverting the .dump() -> .load() above.
                prop.container = ContainerEntity(
                    space=reference_rules.metadata.space,
                    externalId=prop.container.suffix,
                )

        for view in solution_model.views:
            view.implements = None

        if self.exclude_views_in_other_spaces and self._has_views_in_multiple_space(reference_rules):
            solution_model.views = SheetList[DMSView](
                [view for view in solution_model.views if view.view.space == solution_model.metadata.space]
            )

        # Dropping containers coming from reference model
        solution_model.containers = None

        # If reference model on which we are mapping one of Cognite Data Models
        # since we want to affix these with the organization name
        if reference_rules.metadata.as_data_model_id() in COGNITE_MODELS:
            # Remove Cognite affix in view external_id / suffix.
            for prop in solution_model.properties:
                prop.view = self._remove_cognite_affix(prop.view)
                if isinstance(prop.value_type, ViewEntity):
                    prop.value_type = self._remove_cognite_affix(prop.value_type)
            for view in solution_model.views:
                view.view = self._remove_cognite_affix(view.view)
                if view.implements:
                    view.implements = [self._remove_cognite_affix(implemented) for implemented in view.implements]

        if self.mode == "write":
            _, new_containers, new_properties = self._create_new_views(solution_model)
            # Here we add ONLY dummy properties of the solution model and
            # corresponding solution model space containers to hold them
            solution_model.containers = new_containers
            solution_model.properties.extend(new_properties)
        elif self.mode == "read":
            # Inherit view filter from original model to ensure the same instances are returned
            # when querying the new view.
            ref_views_by_external_id = {
                view.view.external_id: view
                for view in reference_rules.views
                if view.view.space == reference_rules.metadata.space
            }
            ref_containers_by_ref_view = defaultdict(set)
            for prop in reference_rules.properties:
                if prop.container:
                    ref_containers_by_ref_view[prop.view].add(prop.container)
            for view in solution_model.views:
                if ref_view := ref_views_by_external_id.get(view.view.external_id):
                    if self.filter_type == "view":
                        view.filter_ = HasDataFilter(inner=[ref_view.view])
                    elif self.filter_type == "container" and (
                        ref_containers := ref_containers_by_ref_view.get(ref_view.view)
                    ):
                        # Sorting to ensure deterministic order
                        view.filter_ = HasDataFilter(inner=sorted(ref_containers))

        return solution_model


class ToDataProductModel(ToSolutionModel):
    type_: ClassVar[str] = "data_product"

    def __init__(
        self,
        new_model_id: DataModelIdentifier,
        org_name: str = "My",
        include: Literal["same-space", "all"] = "same-space",
    ):
        super().__init__(new_model_id, org_name, mode="read", dummy_property=None, exclude_views_in_other_spaces=False)
        self.include = include

    def transform(self, rules: DMSRules) -> DMSRules:
        # Copy to ensure immutability
        expanded = self._expand_properties(rules.model_copy(deep=True))
        if self.include == "same-space":
            expanded.views = SheetList[DMSView](
                [view for view in expanded.views if view.view.space == expanded.metadata.space]
            )
            used_view_entities = {view.view for view in expanded.views}
            expanded.properties = SheetList[DMSProperty](
                [
                    prop
                    for prop in expanded.properties
                    if prop.view.space == expanded.metadata.space
                    and (
                        (isinstance(prop.value_type, ViewEntity) and prop.value_type in used_view_entities)
                        or not isinstance(prop.value_type, ViewEntity)
                    )
                ]
            )

        return self._to_solution(expanded)

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


class ReduceCogniteModel(RulesTransformer[DMSRules, DMSRules]):
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

    def __init__(self, drop: Collection[Literal["3D", "Annotation", "BaseViews"] | str]):
        self.drop_collection = cast(
            list[Literal["3D", "Annotation", "BaseViews"]],
            [collection for collection in drop if collection in self._VIEW_BY_COLLECTION],
        )
        self.drop_external_ids = {external_id for external_id in drop if external_id not in self._VIEW_BY_COLLECTION}

    def transform(self, rules: DMSRules) -> DMSRules:
        verified = rules
        if verified.metadata.as_data_model_id() not in COGNITE_MODELS:
            raise NeatValueError(f"Can only reduce Cognite Data Models, not {verified.metadata.as_data_model_id()}")

        exclude_views = {view for collection in self.drop_collection for view in self._VIEW_BY_COLLECTION[collection]}
        exclude_views |= {view.view.as_id() for view in verified.views if view.view.suffix in self.drop_external_ids}
        new_model = verified.model_copy(deep=True)

        properties_by_view = DMSAnalysis(new_model).classes_with_properties(consider_inheritance=True)

        new_model.views = SheetList[DMSView](
            [view for view in new_model.views if view.view.as_id() not in exclude_views]
        )
        new_properties = SheetList[DMSProperty]()

        for view in new_model.views:
            for prop in properties_by_view[view.view]:
                if self._is_asset_3D_property(prop):
                    # We filter out the 3D property of asset
                    continue
                new_properties.append(prop)

        new_model.properties = new_properties

        return new_model

    def _is_asset_3D_property(self, prop: DMSProperty) -> bool:
        if "3D" not in self.drop_collection:
            return False
        return prop.view.as_id() == self._ASSET_VIEW and prop.view_property == "object3D"

    @property
    def description(self) -> str:
        return f"Removed {len(self.drop_external_ids) + len(self.drop_collection)} views from data model"


class IncludeReferenced(RulesTransformer[DMSRules, DMSRules]):
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


class AddClassImplements(RulesTransformer[InformationRules, InformationRules]):
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


class _InformationRulesConverter:
    _edge_properties: ClassVar[frozenset[str]] = frozenset({"endNode", "end_node", "startNode", "start_node"})

    def __init__(self, information: InformationRules):
        self.rules = information
        self.property_count_by_container: dict[ContainerEntity, int] = defaultdict(int)

    def as_dms_rules(
        self, ignore_undefined_value_types: bool = False, mode: Literal["edge_properties"] | None = None
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
        edge_classes: set[ClassEntity] = set()
        property_to_edge: dict[tuple[ClassEntity, str], ClassEntity] = {}
        end_node_by_edge: dict[ClassEntity, ClassEntity] = {}
        if mode == "edge_properties":
            edge_classes = {
                cls_.class_ for cls_ in self.rules.classes if cls_.implements and cls_.implements[0].suffix == "Edge"
            }
            property_to_edge = {
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
            if prop.class_ in edge_classes and prop.property_ in self._edge_properties:
                continue
            dms_property = self._as_dms_property(
                prop, default_space, default_version, edge_classes, property_to_edge, end_node_by_edge
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
                implements=self._get_view_implements(cls_, info_metadata, mode),
            )

            dms_view.logical = cls_.neatId
            cls_.physical = dms_view.neatId

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
            container = DMSContainer(
                container=container_entity,
                name=class_.name,
                description=class_.description,
                constraint=constrains or None,
            )
            containers.append(container)

        return DMSRules(
            metadata=dms_metadata,
            properties=SheetList[DMSProperty]([prop for prop_set in properties_by_class.values() for prop in prop_set]),
            views=SheetList[DMSView](views),
            containers=SheetList[DMSContainer](containers),
        )

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
        metadata.physical = dms_metadata.identifier

        return dms_metadata

    def _as_dms_property(
        self,
        info_property: InformationProperty,
        default_space: str,
        default_version: str,
        edge_classes: set[ClassEntity],
        property_to_edge: dict[tuple[ClassEntity, str], ClassEntity],
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

        connection = self._get_connection(info_property, value_type, property_to_edge, default_space, default_version)

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
        info_property.physical = dms_property.neatId

        return dms_property

    @staticmethod
    def _get_connection(
        prop: InformationProperty,
        value_type: DataType | ViewEntity | DMSUnknownEntity,
        property_to_edge: dict[tuple[ClassEntity, str], ClassEntity],
        default_space: str,
        default_version: str,
    ) -> Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None:
        if isinstance(value_type, ViewEntity) and (prop.class_, prop.property_) in property_to_edge:
            edge_properties = property_to_edge[(prop.class_, prop.property_)]
            return EdgeEntity(properties=edge_properties.as_view_entity(default_space, default_version))
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

    def _get_view_implements(
        self, cls_: InformationClass, metadata: InformationMetadata, mode: Literal["edge_properties"] | None
    ) -> list[ViewEntity]:
        implements = []
        for parent in cls_.implements or []:
            if mode == "edge_properties" and parent.suffix == "Edge":
                continue
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
    def __init__(self, dms: DMSRules):
        self.dms = dms

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

        classes = [
            InformationClass(
                # we do not want a version in class as we use URI for the class
                class_=ClassEntity(prefix=view.view.prefix, suffix=view.view.suffix),
                description=view.description,
                implements=[
                    # we do not want a version in class as we use URI for the class
                    implemented_view.as_class(skip_version=True)
                    for implemented_view in view.implements or []
                ],
            )
            for view in self.dms.views
        ]

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

            properties.append(
                InformationProperty(
                    # Removing version
                    class_=ClassEntity(suffix=property_.view.suffix, prefix=property_.view.prefix),
                    property_=property_.view_property,
                    value_type=value_type,
                    description=property_.description,
                    min_count=(0 if property_.nullable or property_.nullable is None else 1),
                    max_count=(float("inf") if property_.is_list or property_.nullable is None else 1),
                )
            )

        return InformationRules(
            metadata=metadata,
            properties=SheetList[InformationProperty](properties),
            classes=SheetList[InformationClass](classes),
        )

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
