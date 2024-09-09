import re
import warnings
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from collections.abc import Collection
from datetime import date, datetime
from typing import Literal, TypeVar, cast

from cognite.client.data_classes import data_modeling as dms
from rdflib import Namespace

from cognite.neat.constants import DMS_CONTAINER_PROPERTY_SIZE_LIMIT
from cognite.neat.issues.warnings.user_modeling import ParentInDifferentSpaceWarning
from cognite.neat.rules._shared import JustRules, OutRules, VerifiedRules
from cognite.neat.rules.models import (
    AssetRules,
    DMSRules,
    DomainRules,
    ExtensionCategory,
    InformationRules,
    SchemaCompleteness,
    SheetList,
    data_types,
)
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.dms import DMSMetadata, DMSProperty, DMSView
from cognite.neat.rules.models.entities import (
    AssetEntity,
    AssetFields,
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    EdgeEntity,
    EntityTypes,
    MultiValueTypeInfo,
    ReferenceEntity,
    RelationshipEntity,
    ReverseConnectionEntity,
    UnknownEntity,
    ViewEntity,
)
from cognite.neat.rules.models.information import InformationClass, InformationMetadata, InformationProperty

from ._base import RulesTransformer

T_VerifiedInRules = TypeVar("T_VerifiedInRules", bound=VerifiedRules)
T_VerifiedOutRules = TypeVar("T_VerifiedOutRules", bound=VerifiedRules)


class ConversionTransformer(RulesTransformer[T_VerifiedInRules, T_VerifiedOutRules], ABC):
    """Base class for all conversion transformers."""

    def transform(self, rules: T_VerifiedInRules | OutRules[T_VerifiedInRules]) -> JustRules[T_VerifiedOutRules]:
        out = self._transform(self._to_rules(rules))
        return JustRules(out)

    @abstractmethod
    def _transform(self, rules: T_VerifiedInRules) -> T_VerifiedOutRules:
        raise NotImplementedError()


class InformationToDMS(ConversionTransformer[InformationRules, DMSRules]):
    """Converts InformationRules to DMSRules."""

    def __init__(self, ignore_undefined_value_types: bool = False):
        self.ignore_undefined_value_types = ignore_undefined_value_types

    def _transform(self, rules: InformationRules) -> DMSRules:
        return _InformationRulesConverter(rules).as_dms_rules(self.ignore_undefined_value_types)


class InformationToAsset(ConversionTransformer[InformationRules, AssetRules]):
    """Converts InformationRules to AssetRules."""

    def _transform(self, rules: InformationRules) -> AssetRules:
        return _InformationRulesConverter(rules).as_asset_architect_rules()


class AssetToInformation(ConversionTransformer[AssetRules, InformationRules]):
    """Converts AssetRules to InformationRules."""

    def _transform(self, rules: AssetRules) -> InformationRules:
        return InformationRules.model_validate(rules.model_dump())


class DMSToInformation(ConversionTransformer[DMSRules, InformationRules]):
    """Converts DMSRules to InformationRules."""

    def _transform(self, rules: DMSRules) -> InformationRules:
        return _DMSRulesConverter(rules).as_information_rules()


class ConvertToRules(ConversionTransformer[VerifiedRules, VerifiedRules]):
    """Converts any rules to any rules."""

    def __init__(self, out_cls: type[VerifiedRules]):
        self._out_cls = out_cls

    def _transform(self, rules: VerifiedRules) -> VerifiedRules:
        if isinstance(rules, self._out_cls):
            return rules
        if isinstance(rules, InformationRules) and self._out_cls is DMSRules:
            return InformationToDMS().transform(rules).rules
        if isinstance(rules, InformationRules) and self._out_cls is AssetRules:
            return InformationToAsset().transform(rules).rules
        if isinstance(rules, AssetRules) and self._out_cls is InformationRules:
            return AssetToInformation().transform(rules).rules
        if isinstance(rules, AssetRules) and self._out_cls is DMSRules:
            return InformationToDMS().transform(AssetToInformation().transform(rules)).rules
        if isinstance(rules, DMSRules) and self._out_cls is InformationRules:
            return DMSToInformation().transform(rules).rules
        if isinstance(rules, DMSRules) and self._out_cls is AssetRules:
            return InformationToAsset().transform(DMSToInformation().transform(rules)).rules
        raise ValueError(f"Unsupported conversion from {type(rules)} to {self._out_cls}")


class _InformationRulesConverter:
    def __init__(self, information: InformationRules):
        self.rules = information
        self.is_addition = (
            self.rules.metadata.schema_ is SchemaCompleteness.extended
            and self.rules.metadata.extension is ExtensionCategory.addition
        )
        self.is_reshape = (
            self.rules.metadata.schema_ is SchemaCompleteness.extended
            and self.rules.metadata.extension is ExtensionCategory.reshape
        )
        if self.rules.last:
            self.last_classes = {class_.class_: class_ for class_ in self.rules.last.classes}
        else:
            self.last_classes = {}
        self.property_count_by_container: dict[ContainerEntity, int] = defaultdict(int)

    def as_domain_rules(self) -> DomainRules:
        raise NotImplementedError("DomainRules not implemented yet")

    def as_asset_architect_rules(self) -> "AssetRules":
        from cognite.neat.rules.models.asset._rules import AssetClass, AssetMetadata, AssetProperty, AssetRules

        classes: SheetList[AssetClass] = SheetList[AssetClass](
            data=[AssetClass(**class_.model_dump()) for class_ in self.rules.classes]
        )
        properties: SheetList[AssetProperty] = SheetList[AssetProperty]()
        for prop_ in self.rules.properties:
            if prop_.type_ == EntityTypes.data_property:
                properties.append(
                    AssetProperty(**prop_.model_dump(), implementation=[AssetEntity(property=AssetFields.metadata)])
                )
            elif prop_.type_ == EntityTypes.object_property:
                properties.append(AssetProperty(**prop_.model_dump(), implementation=[RelationshipEntity()]))

        return AssetRules(
            metadata=AssetMetadata(**self.rules.metadata.model_dump()),
            properties=properties,
            classes=classes,
            prefixes=self.rules.prefixes,
        )

    def as_dms_rules(self, ignore_undefined_value_types: bool = False) -> "DMSRules":
        from cognite.neat.rules.models.dms._rules import (
            DMSContainer,
            DMSProperty,
            DMSRules,
            DMSView,
        )

        info_metadata = self.rules.metadata
        default_version = info_metadata.version
        default_space = self._to_space(info_metadata.prefix)
        metadata = self._convert_metadata_to_dms(info_metadata)

        properties_by_class: dict[ClassEntity, list[DMSProperty]] = defaultdict(list)
        referenced_containers: dict[ContainerEntity, Counter[ClassEntity]] = defaultdict(Counter)
        for prop in self.rules.properties:
            if ignore_undefined_value_types and isinstance(prop.value_type, UnknownEntity):
                continue
            dms_property = self._as_dms_property(prop, default_space, default_version)
            properties_by_class[prop.class_].append(dms_property)
            if dms_property.container:
                referenced_containers[dms_property.container][prop.class_] += 1

        views: list[DMSView] = [
            DMSView(
                class_=cls_.class_,
                name=cls_.name,
                view=cls_.class_.as_view_entity(default_space, default_version),
                description=cls_.description,
                reference=cls_.reference,
                implements=self._get_view_implements(cls_, info_metadata),
            )
            for cls_ in self.rules.classes
        ]

        last_dms_rules = _InformationRulesConverter(self.rules.last).as_dms_rules() if self.rules.last else None
        ref_dms_rules = (
            _InformationRulesConverter(self.rules.reference).as_dms_rules() if self.rules.reference else None
        )

        class_by_entity = {cls_.class_: cls_ for cls_ in self.rules.classes}
        if self.rules.last:
            for cls_ in self.rules.last.classes:
                if cls_.class_ not in class_by_entity:
                    class_by_entity[cls_.class_] = cls_

        existing_containers: set[ContainerEntity] = set()
        for rule_set in [last_dms_rules, ref_dms_rules]:
            if rule_set:
                existing_containers.update({c.container for c in rule_set.containers or []})

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
                class_=class_.class_,
                container=container_entity,
                name=class_.name,
                description=class_.description,
                constraint=constrains or None,
            )
            containers.append(container)

        return DMSRules(
            metadata=metadata,
            properties=SheetList[DMSProperty](
                data=[prop for prop_set in properties_by_class.values() for prop in prop_set]
            ),
            views=SheetList[DMSView](data=views),
            containers=SheetList[DMSContainer](data=containers),
            last=last_dms_rules,
            reference=ref_dms_rules,
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
            for parent in class_.parent or []:
                parent_entity = parent.as_container_entity(default_space)
                if parent_entity in referenced_containers:
                    constrains.append(parent_entity)
        return constrains

    @classmethod
    def _convert_metadata_to_dms(cls, metadata: InformationMetadata) -> "DMSMetadata":
        from cognite.neat.rules.models.dms._rules import (
            DMSMetadata,
        )

        space = cls._to_space(metadata.prefix)

        return DMSMetadata(
            schema_=metadata.schema_,
            space=space,
            data_model_type=metadata.data_model_type,
            version=metadata.version,
            external_id=metadata.name.replace(" ", "_").lower(),
            creator=metadata.creator,
            name=metadata.name,
            created=metadata.created,
            updated=metadata.updated,
        )

    def _as_dms_property(self, prop: InformationProperty, default_space: str, default_version: str) -> "DMSProperty":
        """This creates the first"""

        from cognite.neat.rules.models.dms._rules import DMSProperty

        # returns property type, which can be ObjectProperty or DatatypeProperty
        value_type: DataType | ViewEntity | DMSUnknownEntity
        if isinstance(prop.value_type, DataType):
            value_type = prop.value_type
        elif isinstance(prop.value_type, UnknownEntity):
            value_type = DMSUnknownEntity()
        elif isinstance(prop.value_type, ClassEntity):
            value_type = prop.value_type.as_view_entity(default_space, default_version)
        elif isinstance(prop.value_type, MultiValueTypeInfo):
            value_type = self.convert_multi_value_type(prop.value_type)
        else:
            raise ValueError(f"Unsupported value type: {prop.value_type.type_}")

        connection: Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None = None
        if isinstance(value_type, ViewEntity):
            # Default connection type.
            connection = EdgeEntity() if prop.is_list else "direct"

        # defaulting to direct connection
        elif isinstance(value_type, DMSUnknownEntity):
            connection = "direct"

        container: ContainerEntity | None = None
        container_property: str | None = None
        is_list: bool | None = prop.is_list
        nullable: bool | None = not prop.is_mandatory
        if isinstance(connection, EdgeEntity):
            nullable = None
        elif connection == "direct":
            nullable = True
            container, container_property = self._get_container(prop, default_space)
        else:
            container, container_property = self._get_container(prop, default_space)

        return DMSProperty(
            class_=prop.class_,
            name=prop.name,
            property_=prop.property_,
            value_type=value_type,
            nullable=nullable,
            is_list=is_list,
            connection=connection,
            default=prop.default,
            reference=prop.reference,
            container=container,
            container_property=container_property,
            view=prop.class_.as_view_entity(default_space, default_version),
            view_property=prop.property_,
        )

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
        if isinstance(prop.reference, ReferenceEntity):
            return (
                prop.reference.as_container_entity(default_space),
                prop.reference.property_ or prop.property_,
            )
        elif (self.is_addition or self.is_reshape) and prop.class_ in self.last_classes:
            # We need to create a new container for the property, as we cannot change
            # the existing container in the last schema
            container_entity = prop.class_.as_container_entity(default_space)
            container_entity.suffix = self._bump_suffix(container_entity.suffix)
        else:
            container_entity = prop.class_.as_container_entity(default_space)

        while self.property_count_by_container[container_entity] >= DMS_CONTAINER_PROPERTY_SIZE_LIMIT:
            container_entity.suffix = self._bump_suffix(container_entity.suffix)

        self.property_count_by_container[container_entity] += 1
        return container_entity, prop.property_

    def _get_view_implements(self, cls_: InformationClass, metadata: InformationMetadata) -> list[ViewEntity]:
        if isinstance(cls_.reference, ReferenceEntity) and cls_.reference.prefix != metadata.prefix:
            # We use the reference for implements if it is in a different namespace
            if self.rules.reference and cls_.reference.prefix == self.rules.reference.metadata.prefix:
                implements = [
                    cls_.reference.as_view_entity(
                        self.rules.reference.metadata.prefix, self.rules.reference.metadata.version
                    )
                ]
            else:
                implements = [
                    cls_.reference.as_view_entity(metadata.prefix, metadata.version),
                ]
        else:
            implements = []
        for parent in cls_.parent or []:
            if self.rules.reference and parent.prefix == self.rules.reference.metadata.prefix:
                view_entity = parent.as_view_entity(
                    self.rules.reference.metadata.prefix, self.rules.reference.metadata.version
                )
            else:
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
    def convert_multi_value_type(value_type: MultiValueTypeInfo) -> DataType:
        if not all(isinstance(type_, DataType) for type_ in value_type.types):
            raise ValueError("Only MultiValueType with DataType types is supported")
        # We check above that there are no ClassEntity types in the MultiValueType
        py_types = {type_.python for type_ in value_type.types}  # type: ignore[union-attr]
        if dms.Json in py_types and len(py_types) > 1:
            raise ValueError("MultiValueType with Json and other types is not supported")
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

    def as_domain_rules(self) -> "DomainRules":
        raise NotImplementedError("DomainRules not implemented yet")

    def as_information_rules(
        self,
    ) -> "InformationRules":
        from cognite.neat.rules.models.information._rules import (
            InformationClass,
            InformationProperty,
            InformationRules,
        )

        dms = self.dms.metadata

        metadata = self._convert_metadata_to_info(dms)

        classes = [
            InformationClass(
                # we do not want a version in class as we use URI for the class
                class_=ClassEntity(prefix=view.class_.prefix, suffix=view.class_.suffix),
                description=view.description,
                parent=[
                    # we do not want a version in class as we use URI for the class
                    implemented_view.as_class(skip_version=True)
                    # We only want parents in the same namespace, parent in a different namespace is a reference
                    for implemented_view in view.implements or []
                    if implemented_view.prefix == view.class_.prefix
                ],
                reference=self._get_class_reference(view),
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
                    class_=ClassEntity(suffix=property_.class_.suffix, prefix=property_.class_.prefix),
                    property_=property_.view_property,
                    value_type=value_type,
                    description=property_.description,
                    min_count=0 if property_.nullable or property_.nullable is None else 1,
                    max_count=float("inf") if property_.is_list or property_.nullable is None else 1,
                    reference=self._get_property_reference(property_),
                )
            )

        return InformationRules(
            metadata=metadata,
            properties=SheetList[InformationProperty](data=properties),
            classes=SheetList[InformationClass](data=classes),
            last=_DMSRulesConverter(self.dms.last).as_information_rules() if self.dms.last else None,
            reference=_DMSRulesConverter(self.dms.reference).as_information_rules() if self.dms.reference else None,
        )

    @classmethod
    def _convert_metadata_to_info(cls, metadata: DMSMetadata) -> "InformationMetadata":
        from cognite.neat.rules.models.information._rules import InformationMetadata

        prefix = metadata.space
        return InformationMetadata(
            schema_=metadata.schema_,
            data_model_type=metadata.data_model_type,
            extension=metadata.extension,
            prefix=prefix,
            namespace=Namespace(f"https://purl.orgl/neat/{prefix}/"),
            version=metadata.version,
            description=metadata.description,
            name=metadata.name or metadata.external_id,
            creator=metadata.creator,
            created=metadata.created,
            updated=metadata.updated,
        )

    @classmethod
    def _get_class_reference(cls, view: DMSView) -> ReferenceEntity | None:
        parents_other_namespace = [parent for parent in view.implements or [] if parent.prefix != view.class_.prefix]
        if len(parents_other_namespace) == 0:
            return None
        if len(parents_other_namespace) > 1:
            warnings.warn(
                ParentInDifferentSpaceWarning(view.view.as_id()),
                stacklevel=2,
            )
        other_parent = parents_other_namespace[0]

        return ReferenceEntity(prefix=other_parent.prefix, suffix=other_parent.suffix)

    @classmethod
    def _get_property_reference(cls, property_: DMSProperty) -> ReferenceEntity | None:
        has_container_other_namespace = property_.container and property_.container.prefix != property_.class_.prefix
        if not has_container_other_namespace:
            return None
        container = cast(ContainerEntity, property_.container)
        return ReferenceEntity(
            prefix=container.prefix,
            suffix=container.suffix,
            property=property_.container_property,
        )
