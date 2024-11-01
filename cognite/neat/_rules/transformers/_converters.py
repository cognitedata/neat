import re
import warnings
from abc import ABC, abstractmethod
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping
from datetime import date, datetime
from typing import Literal, TypeVar, cast

from cognite.client.data_classes import data_modeling as dms
from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier, ViewId
from rdflib import Namespace

from cognite.neat._constants import COGNITE_MODELS, DMS_CONTAINER_PROPERTY_SIZE_LIMIT
from cognite.neat._issues.errors import NeatValueError
from cognite.neat._issues.warnings._models import (
    EnterpriseModelNotBuildOnTopOfCDMWarning,
    SolutionModelBuildOnTopOfCDMWarning,
)
from cognite.neat._issues.warnings.user_modeling import ParentInDifferentSpaceWarning
from cognite.neat._rules._constants import EntityTypes
from cognite.neat._rules._shared import InputRules, JustRules, OutRules, VerifiedRules
from cognite.neat._rules.analysis import DMSAnalysis
from cognite.neat._rules.models import (
    AssetRules,
    DMSInputRules,
    DMSRules,
    DomainRules,
    ExtensionCategory,
    InformationRules,
    SchemaCompleteness,
    SheetList,
    data_types,
)
from cognite.neat._rules.models.data_types import DataType, String
from cognite.neat._rules.models.dms import DMSMetadata, DMSProperty, DMSView
from cognite.neat._rules.models.dms._rules import DMSContainer
from cognite.neat._rules.models.entities import (
    AssetEntity,
    AssetFields,
    ClassEntity,
    ContainerEntity,
    DMSUnknownEntity,
    EdgeEntity,
    MultiValueTypeInfo,
    ReferenceEntity,
    RelationshipEntity,
    ReverseConnectionEntity,
    UnknownEntity,
    ViewEntity,
)
from cognite.neat._rules.models.information import InformationClass, InformationMetadata, InformationProperty
from cognite.neat._rules.models.information._rules_input import (
    InformationInputClass,
    InformationInputProperty,
    InformationInputRules,
)
from cognite.neat._utils.collection_ import remove_list_elements
from cognite.neat._utils.text import to_camel

from ._base import RulesTransformer

T_VerifiedInRules = TypeVar("T_VerifiedInRules", bound=VerifiedRules)
T_VerifiedOutRules = TypeVar("T_VerifiedOutRules", bound=VerifiedRules)
T_InputInRules = TypeVar("T_InputInRules", bound=InputRules)
T_InputOutRules = TypeVar("T_InputOutRules", bound=InputRules)


class ConversionTransformer(RulesTransformer[T_VerifiedInRules, T_VerifiedOutRules], ABC):
    """Base class for all conversion transformers."""

    def transform(self, rules: T_VerifiedInRules | OutRules[T_VerifiedInRules]) -> JustRules[T_VerifiedOutRules]:
        out = self._transform(self._to_rules(rules))
        return JustRules(out)

    @abstractmethod
    def _transform(self, rules: T_VerifiedInRules) -> T_VerifiedOutRules:
        raise NotImplementedError()


class ToCompliantEntities(RulesTransformer[InformationInputRules, InformationInputRules]):  # type: ignore[misc]
    """Converts input rules to rules with compliant entity IDs that match regex patters used
    by DMS schema components."""

    def transform(
        self, rules: InformationInputRules | OutRules[InformationInputRules]
    ) -> OutRules[InformationInputRules]:
        return JustRules(self._transform(self._to_rules(rules)))

    def _transform(self, rules: InformationInputRules) -> InformationInputRules:
        rules.metadata.prefix = self._fix_entity(rules.metadata.prefix)
        rules.classes = self._fix_classes(rules.classes)
        rules.properties = self._fix_properties(rules.properties)
        return rules

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


_T_Entity = TypeVar("_T_Entity", bound=ClassEntity | ViewEntity)


class SetIDDMSModel(RulesTransformer[DMSRules, DMSRules]):
    def __init__(self, new_id: DataModelId | tuple[str, str, str]):
        self.new_id = DataModelId.load(new_id)

    def transform(self, rules: DMSRules | OutRules[DMSRules]) -> JustRules[DMSRules]:
        if self.new_id.version is None:
            raise NeatValueError("Version is required when setting a new Data Model ID")
        dump = self._to_rules(rules).dump()
        dump["metadata"]["space"] = self.new_id.space
        dump["metadata"]["external_id"] = self.new_id.external_id
        dump["metadata"]["version"] = self.new_id.version
        # Serialize and deserialize to set the new space and external_id
        # as the default values for the new model.
        return JustRules(DMSRules.model_validate(DMSInputRules.load(dump).dump()))


class ToExtension(RulesTransformer[DMSRules, DMSRules]):
    def __init__(
        self,
        new_model_id: DataModelIdentifier,
        org_name: str = "My",
        type_: Literal["enterprise", "solution"] = "enterprise",
        mode: Literal["read", "write"] = "read",
        dummy_property: str = "GUID",
    ):
        self.new_model_id = DataModelId.load(new_model_id)
        if not self.new_model_id.version:
            raise NeatValueError("Version is required for the new model.")

        self.org_name = org_name
        self.mode = mode
        self.type_ = type_
        self.dummy_property = dummy_property

    def transform(self, rules: DMSRules | OutRules[DMSRules]) -> JustRules[DMSRules]:
        # Copy to ensure immutability
        reference_model = self._to_rules(rules)
        reference_model_id = reference_model.metadata.as_data_model_id()

        # if model is solution then we need to get correct space for views and containers
        if self.type_ == "solution":
            if self.mode not in ["read", "write"]:
                raise NeatValueError(f"Unsupported mode: {self.mode}")

            if reference_model_id in COGNITE_MODELS:
                warnings.warn(
                    SolutionModelBuildOnTopOfCDMWarning(reference_model_id=reference_model_id),
                    stacklevel=2,
                )

            return self._to_solution(reference_model)

        elif self.type_ == "enterprise":
            if reference_model_id not in COGNITE_MODELS:
                warnings.warn(
                    EnterpriseModelNotBuildOnTopOfCDMWarning(reference_model_id=reference_model_id).as_message(),
                    stacklevel=2,
                )

            return self._to_enterprise(reference_model)

        else:
            raise NeatValueError(f"Unsupported data model type: {self.type_}")

    def _has_views_in_multiple_space(self, rules: DMSRules) -> bool:
        return any(view.view.space != rules.metadata.space for view in rules.views)

    def _to_solution(self, reference_rules: DMSRules) -> JustRules[DMSRules]:
        """For creation of solution data model / rules specifically for mapping over existing containers."""

        dump = reference_rules.dump()

        # Prepare new model metadata prior validation
        dump["metadata"]["schema_"] = SchemaCompleteness.partial.value
        dump["metadata"]["data_model_type"] = self.type_
        dump["metadata"]["name"] = f"{self.org_name} {self.type_} data model"
        dump["metadata"]["space"] = self.new_model_id.space
        dump["metadata"]["external_id"] = self.new_model_id.external_id
        dump["metadata"]["version"] = self.new_model_id.version

        # dropping reference and last from the dump as they can cause validation
        # issues especially if reference is enterprise model build on top of CDM
        dump.pop("reference", None)
        dump.pop("last", None)

        # Set implement to NONE for all views
        for view in dump["views"]:
            view["implements"] = None

        if self._has_views_in_multiple_space(reference_rules):
            views_to_remove = []
            for view in dump["views"]:
                if ":" in view["view"]:
                    views_to_remove.append(view)

            dump["views"] = remove_list_elements(dump["views"], views_to_remove)

        solution_model = DMSRules.model_validate(DMSInputRules.load(dump).dump())

        # Dropping containers coming from reference model
        solution_model.containers = SheetList[DMSContainer]()

        # We want to map properties to existing containers allowing extension
        for prop in solution_model.properties:
            if prop.container and prop.container.space == self.new_model_id.space:
                prop.container = ContainerEntity(
                    space=reference_rules.metadata.space,
                    externalId=prop.container.suffix,
                )

        # If reference model on which we are mapping one of Cognite Data Models
        # since we want to affix these with the organization name
        if reference_rules.metadata.as_data_model_id() in COGNITE_MODELS:
            # Remove Cognite affix in view external_id / suffix.
            for prop in solution_model.properties:
                prop.view = self._remove_cognite_affix(prop.view)
                prop.class_ = self._remove_cognite_affix(prop.class_)
                if isinstance(prop.value_type, ViewEntity):
                    prop.value_type = self._remove_cognite_affix(prop.value_type)
            for view in solution_model.views:
                view.view = self._remove_cognite_affix(view.view)
                view.class_ = self._remove_cognite_affix(view.class_)

        if self.mode == "write":
            _, new_containers, new_properties = self._get_new_components(solution_model)

            # Here we add ONLY dummy properties of the solution model and
            # corresponding solution model space containers to hold them
            solution_model.containers.extend(new_containers)
            solution_model.properties.extend(new_properties)

        return JustRules(solution_model)

    def _to_enterprise(self, reference_model: DMSRules) -> JustRules[DMSRules]:
        dump = reference_model.dump()

        # This is must prior model validation to avoid validation issues
        dump["metadata"]["schema_"] = SchemaCompleteness.partial.value

        # This will create reference model components in the enterprise model space
        enterprise_model = DMSRules.model_validate(DMSInputRules.load(dump).dump())

        # Post validation metadata update:
        enterprise_model.metadata.name = self.type_
        enterprise_model.metadata.name = f"{self.org_name} {self.type_} data model"
        enterprise_model.metadata.space = self.new_model_id.space
        enterprise_model.metadata.external_id = self.new_model_id.external_id
        enterprise_model.metadata.version = cast(str, self.new_model_id.version)

        if reference_model.metadata.as_data_model_id() in COGNITE_MODELS:
            enterprise_model.reference = reference_model

        # Here we are creating enterprise specific components
        enterprise_views, enterprise_containers, enterprise_properties = self._get_new_components(enterprise_model)

        # And we are adding them to the enterprise model
        # extending reference views with new ones
        enterprise_model.views.extend(enterprise_views)

        # while overwriting containers and properties with new ones
        enterprise_model.containers = enterprise_containers
        enterprise_model.properties = enterprise_properties

        return JustRules(enterprise_model)

    def _remove_cognite_affix(self, entity: _T_Entity) -> _T_Entity:
        """This method removes `Cognite` affix from the entity."""
        new_suffix = entity.suffix.replace("Cognite", self.org_name or "")
        if isinstance(entity, ViewEntity):
            return ViewEntity(space=entity.space, externalId=new_suffix, version=entity.version)  # type: ignore[return-value]
        elif isinstance(entity, ClassEntity):
            return ClassEntity(prefix=entity.prefix, suffix=new_suffix, version=entity.version)  # type: ignore[return-value]
        raise ValueError(f"Unsupported entity type: {type(entity)}")

    def _get_new_components(
        self, rules: DMSRules
    ) -> tuple[SheetList[DMSView], SheetList[DMSContainer], SheetList[DMSProperty]]:
        new_views = SheetList[DMSView]()
        new_containers = SheetList[DMSContainer]()
        new_properties = SheetList[DMSProperty]()

        for definition in rules.views:
            view_entity = self._remove_cognite_affix(definition.view)

            view_entity.version = cast(str, self.new_model_id.version)
            view_entity.prefix = self.new_model_id.space
            container_entity = ContainerEntity(space=view_entity.prefix, externalId=view_entity.external_id)
            class_entity = ClassEntity(prefix=view_entity.prefix, suffix=view_entity.suffix)

            view = DMSView(
                view=view_entity,
                implements=[definition.view],
                in_model=True,
                class_=class_entity,
                name=definition.name,
            )

            container = DMSContainer(
                container=container_entity,
                class_=class_entity,
            )

            property_ = DMSProperty(
                view=view_entity,
                view_property=f"{to_camel(view_entity.suffix)}{self.dummy_property}",
                value_type=String(),
                nullable=True,
                immutable=False,
                is_list=False,
                container=container_entity,
                container_property=f"{to_camel(view_entity.suffix)}{self.dummy_property}",
                class_=class_entity,
                property_=f"{to_camel(view_entity.suffix)}{self.dummy_property}",
            )

            new_properties.append(property_)
            new_views.append(view)
            new_containers.append(container)

        return new_views, new_containers, new_properties


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

    def transform(self, rules: DMSRules | OutRules[DMSRules]) -> JustRules[DMSRules]:
        verified = self._to_rules(rules)
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

        return JustRules(new_model)

    def _is_asset_3D_property(self, prop: DMSProperty) -> bool:
        if "3D" not in self.drop_collection:
            return False
        return prop.view.as_id() == self._ASSET_VIEW and prop.property_ == "object3D"


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
        from cognite.neat._rules.models.asset._rules import AssetClass, AssetMetadata, AssetProperty, AssetRules

        classes: SheetList[AssetClass] = SheetList[AssetClass](
            [AssetClass(**class_.model_dump()) for class_ in self.rules.classes]
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
        from cognite.neat._rules.models.dms._rules import (
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
            properties=SheetList[DMSProperty]([prop for prop_set in properties_by_class.values() for prop in prop_set]),
            views=SheetList[DMSView](views),
            containers=SheetList[DMSContainer](containers),
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
        from cognite.neat._rules.models.dms._rules import (
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

        from cognite.neat._rules.models.dms._rules import DMSProperty

        # returns property type, which can be ObjectProperty or DatatypeProperty
        value_type: DataType | ViewEntity | DMSUnknownEntity
        if isinstance(prop.value_type, DataType):
            value_type = prop.value_type

        # UnknownEntity should  resolve to DMSUnknownEntity
        # meaning end node type is unknown
        elif isinstance(prop.value_type, UnknownEntity):
            value_type = DMSUnknownEntity()

        elif isinstance(prop.value_type, ClassEntity):
            value_type = prop.value_type.as_view_entity(default_space, default_version)

        elif isinstance(prop.value_type, MultiValueTypeInfo):
            # Multi Object type should resolve to DMSUnknownEntity
            # meaning end node type is unknown
            if prop.value_type.is_multi_object_type():
                value_type = DMSUnknownEntity()

            # Multi Data type should resolve to a single data type, or it should
            elif prop.value_type.is_multi_data_type():
                value_type = self.convert_multi_data_type(prop.value_type)

            # Mixed types default to string
            else:
                value_type = String()

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

    def as_domain_rules(self) -> "DomainRules":
        raise NotImplementedError("DomainRules not implemented yet")

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
            properties=SheetList[InformationProperty](properties),
            classes=SheetList[InformationClass](classes),
            last=_DMSRulesConverter(self.dms.last).as_information_rules() if self.dms.last else None,
            reference=_DMSRulesConverter(self.dms.reference).as_information_rules() if self.dms.reference else None,
        )

    @classmethod
    def _convert_metadata_to_info(cls, metadata: DMSMetadata) -> "InformationMetadata":
        from cognite.neat._rules.models.information._rules import InformationMetadata

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
