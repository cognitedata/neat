import re
from collections import defaultdict
from typing import TYPE_CHECKING, Literal

from cognite.neat.rules.models._base import (
    SheetList,
)
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.domain import DomainRules
from cognite.neat.rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    ReferenceEntity,
    UnknownEntity,
    ViewEntity,
    ViewPropertyEntity,
)

from ._rules import InformationClass, InformationMetadata, InformationProperty, InformationRules

if TYPE_CHECKING:
    from cognite.neat.rules.models.dms._rules import DMSMetadata, DMSProperty, DMSRules


class _InformationRulesConverter:
    def __init__(self, information: InformationRules):
        self.information = information

    def as_domain_rules(self) -> DomainRules:
        raise NotImplementedError("DomainRules not implemented yet")

    def as_dms_architect_rules(self) -> "DMSRules":
        from cognite.neat.rules.models.dms._rules import (
            DMSContainer,
            DMSProperty,
            DMSRules,
            DMSView,
        )

        info_metadata = self.information.metadata
        default_version = info_metadata.version
        default_space = self._to_space(info_metadata.prefix)
        metadata = self._convert_metadata_to_dms(info_metadata)

        properties_by_class: dict[str, list[DMSProperty]] = defaultdict(list)
        for prop in self.information.properties:
            properties_by_class[prop.class_.versioned_id].append(
                self._as_dms_property(prop, default_space, default_version)
            )

        views: list[DMSView] = [
            DMSView(
                class_=cls_.class_,
                name=cls_.name,
                view=cls_.class_.as_view_entity(default_space, default_version),
                description=cls_.description,
                reference=cls_.reference,
                implements=self._get_view_implements(cls_, info_metadata),
            )
            for cls_ in self.information.classes
        ]

        classes_without_properties: set[str] = set()
        for class_ in self.information.classes:
            properties: list[DMSProperty] = properties_by_class.get(class_.class_.versioned_id, [])
            if not properties or all(
                isinstance(prop.value_type, ViewPropertyEntity) and prop.connection != "direct" for prop in properties
            ):
                classes_without_properties.add(class_.class_.versioned_id)

        containers: list[DMSContainer] = []
        for class_ in self.information.classes:
            if class_.class_.versioned_id in classes_without_properties:
                continue
            containers.append(
                DMSContainer(
                    class_=class_.class_,
                    name=class_.name,
                    container=class_.class_.as_container_entity(default_space),
                    description=class_.description,
                    constraint=[
                        parent.as_container_entity(default_space)
                        for parent in class_.parent or []
                        if parent.versioned_id not in classes_without_properties
                    ]
                    or None,
                )
            )

        return DMSRules(
            metadata=metadata,
            properties=SheetList[DMSProperty](
                data=[prop for prop_set in properties_by_class.values() for prop in prop_set]
            ),
            views=SheetList[DMSView](data=views),
            containers=SheetList[DMSContainer](data=containers),
            last=self.information.last.as_dms_architect_rules() if self.information.last else None,
            reference=self.information.reference.as_dms_architect_rules() if self.information.reference else None,
        )

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

    @classmethod
    def _as_dms_property(cls, prop: InformationProperty, default_space: str, default_version: str) -> DMSProperty:
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
            container, container_property = cls._get_container(prop, default_space)
        else:
            container, container_property = cls._get_container(prop, default_space)

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

    @classmethod
    def _get_container(cls, prop: InformationProperty, default_space: str) -> tuple[ContainerEntity, str]:
        if isinstance(prop.reference, ReferenceEntity):
            return (
                prop.reference.as_container_entity(default_space),
                prop.reference.property_ or prop.property_,
            )
        else:
            return prop.class_.as_container_entity(default_space), prop.property_

    @classmethod
    def _get_view_implements(cls, cls_: InformationClass, metadata: InformationMetadata) -> list[ViewEntity]:
        if isinstance(cls_.reference, ReferenceEntity) and cls_.reference.prefix != metadata.prefix:
            # We use the reference for implements if it is in a different namespace
            implements = [
                cls_.reference.as_view_entity(metadata.prefix, metadata.version),
            ]
        else:
            implements = []

        implements.extend([parent.as_view_entity(metadata.prefix, metadata.version) for parent in cls_.parent or []])
        return implements
