import warnings
from datetime import datetime
from typing import cast

from rdflib import Namespace

from cognite.neat.rules import issues
from cognite.neat.rules.models._base import SheetList
from cognite.neat.rules.models.data_types import DataType
from cognite.neat.rules.models.domain import DomainRules
from cognite.neat.rules.models.entities import (
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    ParentClassEntity,
    ReferenceEntity,
    UnknownEntity,
    ViewEntity,
    ViewPropertyEntity,
)
from cognite.neat.rules.models.information._rules import InformationRules

from ._rules import DMSProperty, DMSRules, DMSView


class _DMSRulesConverter:
    def __init__(self, dms: DMSRules):
        self.dms = dms

    def as_domain_rules(self) -> "DomainRules":
        raise NotImplementedError("DomainRules not implemented yet")

    def as_information_architect_rules(
        self,
        created: datetime | None = None,
        updated: datetime | None = None,
        name: str | None = None,
        namespace: Namespace | None = None,
    ) -> "InformationRules":
        from cognite.neat.rules.models.information._rules import (
            InformationClass,
            InformationMetadata,
            InformationProperty,
            InformationRules,
        )

        dms = self.dms.metadata
        prefix = dms.space

        metadata = InformationMetadata(
            schema_=dms.schema_,
            prefix=prefix,
            namespace=namespace or Namespace(f"https://purl.orgl/neat/{prefix}/"),
            version=dms.version,
            name=name or dms.name or "Missing name",
            creator=dms.creator,
            created=dms.created or created or datetime.now(),
            updated=dms.updated or updated or datetime.now(),
        )

        classes = [
            InformationClass(
                # we do not want a version in class as we use URI for the class
                class_=ClassEntity(prefix=view.class_.prefix, suffix=view.class_.suffix),
                description=view.description,
                parent=[
                    # we do not want a version in class as we use URI for the class
                    ParentClassEntity(prefix=implemented_view.prefix, suffix=implemented_view.suffix)
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
            elif isinstance(property_.value_type, ViewEntity | ViewPropertyEntity):
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
            reference=self.dms.reference and self.dms.reference.as_information_architect_rules(),  # type: ignore[arg-type]
        )

    @classmethod
    def _get_class_reference(cls, view: DMSView) -> ReferenceEntity | None:
        parents_other_namespace = [parent for parent in view.implements or [] if parent.prefix != view.class_.prefix]
        if len(parents_other_namespace) == 0:
            return None
        if len(parents_other_namespace) > 1:
            warnings.warn(
                issues.dms.MultipleReferenceWarning(
                    view_id=view.view.as_id(), implements=[v.as_id() for v in parents_other_namespace]
                ),
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
