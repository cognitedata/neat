from collections import Counter
from collections.abc import Callable, Sequence

from cognite.neat._issues import IssueList
from cognite.neat._issues.errors import (
    PropertyTypeNotSupportedError,
    ResourceMissingIdentifierError,
    ResourceNotFoundError,
)
from cognite.neat._issues.warnings import PropertyTypeNotSupportedWarning, ResourceTypeNotSupportedWarning
from cognite.neat._rules.importers._dtdl2rules.spec import (
    DTMI,
    Command,
    CommandV2,
    Component,
    DTDLBase,
    DTDLBaseWithName,
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
from cognite.neat._rules.models.data_types import _DATA_TYPE_BY_NAME, DataType, Json, String
from cognite.neat._rules.models.entities import ClassEntity
from cognite.neat._rules.models.information import (
    InformationInputClass,
    InformationInputProperty,
)


class _DTDLConverter:
    def __init__(self, issues: IssueList | None = None) -> None:
        self.issues = IssueList(issues or [])
        self.properties: list[InformationInputProperty] = []
        self.classes: list[InformationInputClass] = []
        self._item_by_id: dict[DTMI, DTDLBase] = {}

        self._method_by_type = {
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

    def get_most_common_prefix(self) -> str:
        if not self.classes:
            raise ValueError("No classes found")
        counted = Counter(
            class_.prefix
            for class_ in (cls_.class_ for cls_ in self.classes)
            if isinstance(class_, ClassEntity) and isinstance(class_.prefix, str)
        )
        if not counted:
            raise ValueError("No prefixes found")
        return counted.most_common(1)[0][0]

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
        # Bug in mypy https://github.com/python/mypy/issues/17478
        convert_method: Callable[[DTDLBase, str | None], None] | None = self._method_by_type.get(type(item))  # type: ignore[assignment]
        if convert_method is not None:
            convert_method(item, parent)
        else:
            self.issues.append(
                ResourceTypeNotSupportedWarning(
                    item.identifier_with_fallback,
                    item.type,
                ),
            )

    def convert_interface(self, item: Interface, _: str | None) -> None:
        class_ = InformationInputClass(
            class_=item.id_.as_class_id(),
            name=item.display_name,
            description=item.description,
            implements=[parent.as_class_id() for parent in item.extends or []] or None,
        )
        self.classes.append(class_)
        for sub_item_or_id in item.contents or []:
            if isinstance(sub_item_or_id, DTMI) and sub_item_or_id not in self._item_by_id:
                self.issues.append(
                    PropertyTypeNotSupportedWarning(
                        item.id_.model_dump() or item.display_name or "missing",
                        item.type,
                        sub_item_or_id.path[-1],
                        ".".join(sub_item_or_id.path),
                    )
                )
            elif isinstance(sub_item_or_id, DTMI):
                sub_item = self._item_by_id[sub_item_or_id]
                self.convert_item(sub_item, class_.class_str)
            else:
                self.convert_item(sub_item_or_id, class_.class_str)
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

        prop = InformationInputProperty(
            class_=ClassEntity.load(parent),
            property_=item.name,
            name=item.display_name,
            description=item.description,
            value_type=value_type,
            min_count=min_count,
            max_count=max_count,
        )
        self.properties.append(prop)

    def _missing_parent_warning(self, item: DTDLBaseWithName):
        self.issues.append(
            ResourceNotFoundError(
                "UNKNOWN",
                "parent",
                item.identifier_with_fallback,
                item.type,
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
                ResourceTypeNotSupportedWarning[str](
                    item.identifier_with_fallback,
                    f"{item.type}.request",
                ),
            )
            return None
        if item.response is not None:
            # Currently, we do not know how to handle response
            self.issues.append(ResourceTypeNotSupportedWarning[str](f"{parent}.response", "Command.Response"))
        value_type = self.schema_to_value_type(item.request.schema_, item)
        if value_type is None:
            return
        prop = InformationInputProperty(
            class_=ClassEntity.load(parent),
            property_=item.name,
            name=item.display_name,
            description=item.description,
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
        prop = InformationInputProperty(
            class_=ClassEntity.load(parent),
            property_=item.name,
            name=item.display_name,
            description=item.description,
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
            value_type: DataType | ClassEntity
            if item.target in self._item_by_id:
                value_type = item.target.as_class_id()
            else:
                # Falling back to json
                self.issues.append(
                    ResourceMissingIdentifierError(
                        "unknown",
                        item.target.model_dump(),
                    )
                )
                value_type = Json()

            prop = InformationInputProperty(
                class_=ClassEntity.load(parent),
                property_=item.name,
                name=item.display_name,
                description=item.description,
                min_count=item.min_multiplicity or 0,
                max_count=item.max_multiplicity or 1,
                value_type=value_type,
            )
            self.properties.append(prop)
        elif item.properties is not None:
            for prop_ in item.properties or []:
                self.convert_property(prop_, parent, item.min_multiplicity, item.max_multiplicity)

    def convert_object(self, item: Object, _: str | None) -> None:
        if item.id_ is None:
            self.issues.append(
                ResourceMissingIdentifierError(
                    resource_type=item.type,
                    name=item.display_name,
                )
            )
            return None

        class_ = InformationInputClass(
            class_=item.id_.as_class_id(),
            name=item.display_name,
            description=item.description,
        )
        self.classes.append(class_)

        for field_ in item.fields or []:
            value_type = self.schema_to_value_type(field_.schema_, item)
            if value_type is None:
                continue
            prop = InformationInputProperty(
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
    ) -> DataType | ClassEntity | None:
        input_type = self._item_by_id.get(schema) if isinstance(schema, DTMI) else schema

        if isinstance(input_type, Enum):
            return String()
        elif isinstance(input_type, str) and input_type.casefold() in _DATA_TYPE_BY_NAME:
            return _DATA_TYPE_BY_NAME[input_type.casefold()]()
        elif isinstance(input_type, str):
            self.issues.append(
                PropertyTypeNotSupportedError(
                    item.identifier_with_fallback,
                    item.type,
                    "schema",
                    input_type,
                )
            )
            return None
        elif isinstance(input_type, Object | Interface):
            if input_type.id_ is None:
                self.issues.append(
                    ResourceMissingIdentifierError(
                        input_type.type,
                        input_type.display_name,
                    )
                )
                return Json()
            else:
                if isinstance(input_type, Object):
                    self.convert_object(input_type, None)
                return input_type.id_.as_class_id()
        else:
            self.issues.append(
                PropertyTypeNotSupportedWarning(
                    item.identifier_with_fallback,
                    item.type,  # type: ignore[arg-type]
                    "schema",
                    input_type.type if input_type else "missing",
                )
            )
            return None
