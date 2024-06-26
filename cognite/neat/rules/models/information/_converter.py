import re
from collections import Counter, defaultdict
from collections.abc import Collection
from datetime import date, datetime
from typing import TYPE_CHECKING, Literal

from cognite.client.data_classes import data_modeling as dms

from cognite.neat.rules.models import data_types
from cognite.neat.rules.models._base import (
    ExtensionCategory,
    SchemaCompleteness,
    SheetList,
)
from cognite.neat.rules.models._constants import DMS_CONTAINER_SIZE_LIMIT
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.domain import DomainRules
from cognite.neat.rules.models.entities import (
    AssetEntity,
    AssetFields,
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    EntityTypes,
    MultiValueTypeInfo,
    ReferenceEntity,
    RelationshipEntity,
    UnknownEntity,
    ViewEntity,
    ViewPropertyEntity,
)

from ._rules import InformationClass, InformationMetadata, InformationProperty, InformationRules

if TYPE_CHECKING:
    from cognite.neat.rules.models.asset._rules import AssetRules
    from cognite.neat.rules.models.dms._rules import DMSMetadata, DMSProperty, DMSRules


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

    def as_dms_architect_rules(self) -> "DMSRules":
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

        last_dms_rules = self.rules.last.as_dms_architect_rules() if self.rules.last else None
        ref_dms_rules = self.rules.reference.as_dms_architect_rules() if self.rules.reference else None

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
        value_type: DataType | ViewEntity | ViewPropertyEntity | DMSUnknownEntity
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

        relation: Literal["direct", "edge", "reverse"] | None = None
        if isinstance(value_type, ViewEntity | ViewPropertyEntity):
            relation = "edge" if prop.is_list else "direct"

        container: ContainerEntity | None = None
        container_property: str | None = None
        is_list: bool | None = prop.is_list
        nullable: bool | None = not prop.is_mandatory
        if relation == "edge":
            nullable = None
        elif relation == "direct":
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
            connection=relation,
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

        while self.property_count_by_container[container_entity] >= DMS_CONTAINER_SIZE_LIMIT:
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
