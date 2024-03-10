from collections.abc import Callable, Sequence

from cognite.neat.rules import validation
from cognite.neat.rules.importers._dtdl2rules.spec import (
    DTMI,
    Command,
    CommandV2,
    Component,
    DTDLBase,
    Enum,
    Interface,
    Object,
    Property,
    PropertyV2,
    Relationship,
    Schema,
    Telemetry,
    TelemetryV2,
)
from cognite.neat.rules.models._rules._types import (
    XSD_VALUE_TYPE_MAPPINGS,
    ClassEntity,
    ParentClassEntity,
    XSDValueType,
)
from cognite.neat.rules.models._rules.information_rules import InformationClass, InformationProperty
from cognite.neat.rules.validation import IssueList, ValidationIssue


class _DTDLConverter:
    def __init__(self, issues: list[ValidationIssue] | None = None) -> None:
        self.issues: IssueList = IssueList(issues or [])
        self.properties: list[InformationProperty] = []
        self.classes: list[InformationClass] = []
        self._item_by_id: dict[DTMI, DTDLBase] = {}

        self._method_by_type: dict[type[DTDLBase], Callable[[DTDLBase, str | None], None]] = {
            Interface: self.convert_interface,  # type: ignore[dict-item]
            Property: self.convert_property,  # type: ignore[dict-item]
            PropertyV2: self.convert_property,  # type: ignore[dict-item]
            Relationship: self.convert_relationship,  # type: ignore[dict-item]
            Object: self.convert_object,  # type: ignore[dict-item]
            Telemetry: self.convert_telemetry,  # type: ignore[dict-item]
            TelemetryV2: self.convert_telemetry,  # type: ignore[dict-item]
            Command: self.convert_command,  # type: ignore[dict-item]
            CommandV2: self.convert_command,  # type: ignore[dict-item]
            Component: self.convert_component,  # type: ignore[dict-item]
        }

    def convert(self, items: Sequence[DTDLBase]) -> None:
        self._item_by_id.update({item.id_: item for item in items if item.id_ is not None})
        # Update schema objects which are reusable
        self._item_by_id.update(
            {
                schema.id_: schema
                for item in items
                if isinstance(item, Interface)
                for schema in item.schemas or []
                if isinstance(schema.id_, DTMI) and isinstance(schema, DTDLBase)
            }
        )

        for item in items:
            self.convert_item(item)

    def convert_item(self, item: DTDLBase, parent: str | None = None) -> None:
        convert_method = self._method_by_type.get(type(item))
        if convert_method is not None:
            convert_method(item, parent)
        else:
            self.issues.append(
                validation.UnknownComponent(
                    component_type=item.type,
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )

    def convert_interface(self, item: Interface, _: str | None) -> None:
        class_ = InformationClass(
            class_=item.id_.as_class_id(),
            name=item.display_name,
            description=item.description,
            comment=item.comment,
            parent=[ParentClassEntity.from_raw(parent.as_class_id()) for parent in item.extends or []] or None,
        )
        self.classes.append(class_)
        for sub_item_or_id in item.contents or []:
            if isinstance(sub_item_or_id, DTMI) and sub_item_or_id not in self._item_by_id:
                self.issues.append(
                    validation.UnknownProperty(
                        component_type=item.type,
                        property_name=sub_item_or_id.path[-1],
                        instance_name=item.display_name,
                        instance_id=item.id_.model_dump(),
                    )
                )
            elif isinstance(sub_item_or_id, DTMI):
                sub_item = self._item_by_id[sub_item_or_id]
                self.convert_item(sub_item, class_.class_.versioned_id)
            else:
                self.convert_item(sub_item_or_id, class_.class_.versioned_id)
        # interface.schema objects are handled in the convert method

    def convert_property(
        self, item: Property | Telemetry, parent: str | None, min_count: int | None = 0, max_count: int | None = 1
    ) -> None:
        if parent is None:
            self._missing_parent_warning(item)
            return None
        value_type = self.schema_to_value_type(item.schema_, item)
        if value_type is None:
            return None

        prop = InformationProperty(
            class_=ClassEntity.from_raw(parent),
            property_=item.name,
            name=item.display_name,
            description=item.description,
            comment=item.comment,
            value_type=value_type,
            min_count=min_count,
            max_count=max_count,
        )
        self.properties.append(prop)

    def _missing_parent_warning(self, item):
        self.issues.append(
            validation.MissingParentDefinition(
                component_type=item.type,
                instance_name=item.display_name,
                instance_id=item.id_.model_dump() if item.id_ else None,
            )
        )

    def convert_telemetry(self, item: Telemetry, parent: str | None) -> None:
        return self.convert_property(
            item,
            parent,
        )

    def convert_command(self, item: Command | CommandV2, parent: str | None) -> None:
        if parent is None:
            self._missing_parent_warning(item)
            return None
        if item.request is None:
            self.issues.append(
                validation.UnknownSubComponent(
                    component_type=item.type,
                    sub_component="request",
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )
            return None
        if item.response is not None:
            # Currently, we do not know how to handle response
            self.issues.append(
                validation.ImportIgnored(
                    identifier=f"{parent}.response",
                    reason="Neat does not have a concept of response for commands. This will be ignored.",
                )
            )
        value_type = self.schema_to_value_type(item.request.schema_, item)
        if value_type is None:
            return
        prop = InformationProperty(
            class_=ClassEntity.from_raw(parent),
            property_=item.name,
            name=item.display_name,
            description=item.description,
            comment=item.comment,
            value_type=value_type,
            min_count=0,
            max_count=1,
        )
        self.properties.append(prop)

    def convert_component(self, item: Component, parent: str | None) -> None:
        if parent is None:
            self._missing_parent_warning(item)
            return None

        value_type = self.schema_to_value_type(item.schema_, item)
        if value_type is None:
            return
        prop = InformationProperty(
            class_=ClassEntity.from_raw(parent),
            property_=item.name,
            name=item.display_name,
            description=item.description,
            comment=item.comment,
            value_type=value_type,
            min_count=0,
            max_count=1,
        )
        self.properties.append(prop)

    def convert_relationship(self, item: Relationship, parent: str | None) -> None:
        if parent is None:
            self._missing_parent_warning(item)
            return None
        if item.target is not None:
            value_type: XSDValueType | ClassEntity
            if item.target in self._item_by_id:
                value_type = item.target.as_class_id()
            else:
                # Falling back to json
                self.issues.append(
                    validation.MissingIdentifier(
                        component_type="Unknown",
                        instance_name=item.target.model_dump(),
                        instance_id=item.target.model_dump(),
                    )
                )
                value_type = XSD_VALUE_TYPE_MAPPINGS["json"]

            prop = InformationProperty(
                class_=ClassEntity.from_raw(parent),
                property_=item.name,
                name=item.display_name,
                description=item.description,
                min_count=item.min_multiplicity or 0,
                max_count=item.max_multiplicity or 1,
                comment=item.comment,
                value_type=value_type,
            )
            self.properties.append(prop)
        elif item.properties is not None:
            for prop_ in item.properties or []:
                self.convert_property(prop_, parent, item.min_multiplicity, item.max_multiplicity)

    def convert_object(self, item: Object, _: str | None) -> None:
        if item.id_ is None:
            self.issues.append(
                validation.MissingIdentifier(
                    component_type=item.type,
                    instance_name=item.display_name,
                )
            )
            return None

        class_ = InformationClass(
            class_=item.id_.as_class_id(),
            name=item.display_name,
            description=item.description,
            comment=item.comment,
        )
        self.classes.append(class_)

        for field_ in item.fields or []:
            value_type = self.schema_to_value_type(field_.schema_, item)
            if value_type is None:
                continue
            prop = InformationProperty(
                class_=class_.class_,
                name=field_.name,
                description=field_.description,
                property_=field_.name,
                value_type=value_type,
                min_count=0,
                max_count=1,
            )
            self.properties.append(prop)

    def schema_to_value_type(
        self, schema: Schema | Interface | DTMI | None, item: DTDLBase
    ) -> XSDValueType | ClassEntity | None:
        input_type = self._item_by_id.get(schema) if isinstance(schema, DTMI) else schema

        if isinstance(input_type, Enum):
            return XSD_VALUE_TYPE_MAPPINGS["string"]
        elif isinstance(input_type, str) and input_type in XSD_VALUE_TYPE_MAPPINGS:
            return XSD_VALUE_TYPE_MAPPINGS[input_type]
        elif isinstance(input_type, str):
            self.issues.append(
                validation.UnsupportedPropertyType(
                    component_type=item.type,
                    property_type=input_type,
                    property_name="schema",
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )
            return None
        elif isinstance(input_type, Object | Interface):
            if input_type.id_ is None:
                self.issues.append(
                    validation.MissingIdentifier(
                        component_type=input_type.type,
                        instance_name=input_type.display_name,
                    )
                )
                return XSD_VALUE_TYPE_MAPPINGS["json"]
            else:
                if isinstance(input_type, Object):
                    self.convert_object(input_type, None)
                return ClassEntity.from_raw(input_type.id_.as_class_id())
        else:
            self.issues.append(
                validation.UnknownProperty(
                    component_type=item.type,
                    property_name="schema",
                    instance_name=item.display_name,
                    instance_id=item.id_.model_dump() if item.id_ else None,
                )
            )
            return None
