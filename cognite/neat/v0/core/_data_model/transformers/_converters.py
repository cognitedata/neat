import re
import urllib.parse
import warnings
from abc import ABC
from collections import Counter, defaultdict
from collections.abc import Collection, Mapping
from datetime import date, datetime
from functools import cached_property
from graphlib import CycleError, TopologicalSorter
from typing import Any, ClassVar, Literal, TypeVar, cast, overload

from cognite.client import data_modeling as dm
from cognite.client.data_classes import data_modeling as dms
from cognite.client.data_classes.data_modeling import DataModelId, DataModelIdentifier, View, ViewId
from cognite.client.utils.useful_types import SequenceNotStr
from pydantic import ValidationError
from rdflib import Namespace

from cognite.neat.v0.core._client import NeatClient
from cognite.neat.v0.core._client.data_classes.data_modeling import (
    ContainerApplyDict,
    ViewApplyDict,
)
from cognite.neat.v0.core._constants import (
    COGNITE_CONCEPTS,
    COGNITE_MODELS,
    COGNITE_SPACES,
    DMS_CONTAINER_PROPERTY_SIZE_LIMIT,
    DMS_RESERVED_PROPERTIES,
    get_default_prefixes_and_namespaces,
)
from cognite.neat.v0.core._data_model._constants import CONSTRAINT_ID_MAX_LENGTH, PATTERNS, get_reserved_words
from cognite.neat.v0.core._data_model._shared import (
    ImportContext,
    ImportedDataModel,
    ImportedUnverifiedDataModel,
    VerifiedDataModel,
)
from cognite.neat.v0.core._data_model.analysis import DataModelAnalysis
from cognite.neat.v0.core._data_model.importers import DMSImporter
from cognite.neat.v0.core._data_model.models import (
    ConceptualDataModel,
    PhysicalDataModel,
    SheetList,
    UnverifiedConceptualDataModel,
    UnverifiedPhysicalDataModel,
    data_types,
)
from cognite.neat.v0.core._data_model.models.conceptual import (
    Concept,
    ConceptualMetadata,
    ConceptualProperty,
    UnverifiedConcept,
    UnverifiedConceptualProperty,
)
from cognite.neat.v0.core._data_model.models.data_types import (
    AnyURI,
    DataType,
    Enum,
    File,
    String,
    Timeseries,
)
from cognite.neat.v0.core._data_model.models.entities import (
    ConceptEntity,
    ContainerEntity,
    EdgeEntity,
    HasDataFilter,
    MultiValueTypeInfo,
    PhysicalUnknownEntity,
    ReverseConnectionEntity,
    UnknownEntity,
    ViewEntity,
)
from cognite.neat.v0.core._data_model.models.entities._single_value import ContainerConstraintEntity
from cognite.neat.v0.core._data_model.models.physical import (
    PhysicalMetadata,
    PhysicalProperty,
    PhysicalValidation,
    PhysicalView,
)
from cognite.neat.v0.core._data_model.models.physical._verified import (
    PhysicalContainer,
    PhysicalEnum,
    PhysicalNodeType,
)
from cognite.neat.v0.core._issues import IssueList
from cognite.neat.v0.core._issues._factory import from_pydantic_errors
from cognite.neat.v0.core._issues.errors import CDFMissingClientError, NeatValueError
from cognite.neat.v0.core._issues.warnings import (
    NeatValueWarning,
    PropertyOverwritingWarning,
)
from cognite.neat.v0.core._issues.warnings._models import (
    SolutionModelBuildOnTopOfCDMWarning,
)
from cognite.neat.v0.core._utils.rdf_ import get_inheritance_path
from cognite.neat.v0.core._utils.text import (
    NamingStandardization,
    humanize_collection,
    title,
    to_camel_case,
    to_words,
)

from ._base import (
    DataModelTransformer,
    T_VerifiedIn,
    T_VerifiedOut,
    VerifiedDataModelTransformer,
)
from ._verification import VerifyPhysicalDataModel

T_UnverifiedInDataModel = TypeVar("T_UnverifiedInDataModel", bound=ImportedUnverifiedDataModel)
T_UnverifiedOutDataModel = TypeVar("T_UnverifiedOutDataModel", bound=ImportedUnverifiedDataModel)


class ConversionTransformer(VerifiedDataModelTransformer[T_VerifiedIn, T_VerifiedOut], ABC):
    """Base class for all conversion transformers."""

    ...


class ToDMSCompliantEntities(
    DataModelTransformer[
        ImportedDataModel[UnverifiedConceptualDataModel],
        ImportedDataModel[UnverifiedConceptualDataModel],
    ]
):
    """Makes concept and property ids compliant with DMS regex restrictions.


    Args:
        rename_warning: How to handle renaming of entities that are not compliant with the Information Model.
            - "raise": Raises a warning and renames the entity.
            - "skip": Renames the entity without raising a warning.
    """

    def __init__(self, rename_warning: Literal["raise", "skip"] = "skip") -> None:
        self._renaming = rename_warning

    @property
    def description(self) -> str:
        return "Ensures that all entities are compliant with the Information Model."

    def transform(
        self, data_model: ImportedDataModel[UnverifiedConceptualDataModel]
    ) -> ImportedDataModel[UnverifiedConceptualDataModel]:
        if data_model.unverified_data_model is None:
            return data_model
        # Doing dump to obtain a copy, and ensure that all entities are created. Input allows
        # string for entities, the dump call will convert these to entities.
        dumped = data_model.unverified_data_model.dump()
        copy = UnverifiedConceptualDataModel.load(dumped)

        new_by_old_concept_suffix: dict[str, str] = {}
        for concept in copy.concepts:
            concept_entity = cast(ConceptEntity, concept.concept)  # Safe due to the dump above
            if not PATTERNS.view_id_compliance.match(concept_entity.suffix):
                new_suffix = self._fix_concept_suffix(concept_entity.suffix)
                if self._renaming == "raise":
                    warnings.warn(
                        NeatValueWarning(f"Invalid class name {concept_entity.suffix!r}.Renaming to {new_suffix}"),
                        stacklevel=2,
                    )
                concept.concept.suffix = new_suffix  # type: ignore[union-attr]

        for concept in copy.concepts:
            if concept.implements:
                for i, parent in enumerate(concept.implements):
                    if isinstance(parent, ConceptEntity) and parent.suffix in new_by_old_concept_suffix:
                        concept.implements[i].suffix = new_by_old_concept_suffix[parent.suffix]  # type: ignore[union-attr]

        for prop in copy.properties:
            if not PATTERNS.physical_property_id_compliance.match(prop.property_):
                new_property = self._fix_property(prop.property_)
                if self._renaming == "warning":
                    warnings.warn(
                        NeatValueWarning(
                            f"Invalid property name {prop.concept.suffix}.{prop.property_!r}."
                            f" Renaming to {new_property}"
                            # type: ignore[union-attr]
                        ),
                        stacklevel=2,
                    )
                prop.property_ = new_property

            if isinstance(prop.concept, ConceptEntity) and prop.concept.suffix in new_by_old_concept_suffix:
                prop.concept.suffix = new_by_old_concept_suffix[prop.concept.suffix]

            if isinstance(prop.value_type, ConceptEntity) and prop.value_type.suffix in new_by_old_concept_suffix:
                prop.value_type.suffix = new_by_old_concept_suffix[prop.value_type.suffix]

            if isinstance(prop.value_type, MultiValueTypeInfo):
                for i, value_type in enumerate(prop.value_type.types):
                    if isinstance(value_type, ConceptEntity) and value_type.suffix in new_by_old_concept_suffix:
                        prop.value_type.types[i].suffix = new_by_old_concept_suffix[value_type.suffix]  # type: ignore[union-attr]

        return ImportedDataModel(unverified_data_model=copy, context=data_model.context)

    @cached_property
    def _reserved_concept_words(self) -> set[str]:
        return set(get_reserved_words("concept"))

    @cached_property
    def _reserved_property_words(self) -> set[str]:
        return set(get_reserved_words("property"))

    def _fix_concept_suffix(self, suffix: str) -> str:
        if suffix in self._reserved_concept_words:
            return f"My{suffix}"
        suffix = urllib.parse.unquote(suffix)
        suffix = NamingStandardization.standardize_concept_str(suffix)
        if len(suffix) > 252:
            suffix = suffix[:252]
        return suffix

    def _fix_property(self, property_: str) -> str:
        if property_ in self._reserved_property_words:
            return f"my{property_}"
        property_ = urllib.parse.unquote(property_)
        property_ = NamingStandardization.standardize_property_str(property_)
        if len(property_) > 252:
            property_ = property_[:252]
        return property_


class StandardizeSpaceAndVersion(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel]):  # type: ignore[misc]
    """This transformer standardizes the space and version of the physical data model.

    typically used to ensure all the views are moved to the same version as the data model.

    """

    @property
    def description(self) -> str:
        return "Ensures uniform version and space of the views belonging to the data model."

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        copy = data_model.model_copy(deep=True)

        space = copy.metadata.space
        version = copy.metadata.version

        copy.views = self._standardize_views(copy.views, space, version)
        copy.properties = self._standardize_properties(copy.properties, space, version)
        return copy

    def _standardize_views(self, views: SheetList[PhysicalView], space: str, version: str) -> SheetList[PhysicalView]:
        for view in views:
            if view.view.space not in COGNITE_SPACES:
                view.view.version = version
                view.view.prefix = space

            if view.implements:
                for i, parent in enumerate(view.implements):
                    if parent.space not in COGNITE_SPACES:
                        view.implements[i].version = version
                        view.implements[i].prefix = space
        return views

    def _standardize_properties(
        self, properties: SheetList[PhysicalProperty], space: str, version: str
    ) -> SheetList[PhysicalProperty]:
        for property_ in properties:
            if property_.view.space not in COGNITE_SPACES:
                property_.view.version = version
                property_.view.prefix = space

            if isinstance(property_.value_type, ViewEntity) and property_.value_type.space not in COGNITE_SPACES:
                property_.value_type.version = version
                property_.value_type.prefix = space

            # for edge connection
            if (
                property_.connection
                and isinstance(property_.connection, EdgeEntity)
                and property_.connection.properties
            ):
                if property_.connection.properties.space not in COGNITE_SPACES:
                    property_.connection.properties.version = version
                    property_.connection.properties.prefix = space

        return properties


class ToCompliantEntities(VerifiedDataModelTransformer[ConceptualDataModel, ConceptualDataModel]):  # type: ignore[misc]
    """Converts input data_model to data_model with compliant entity IDs that match regex patters used
    by DMS schema components."""

    @property
    def description(self) -> str:
        return "Ensures externalIDs are compliant with CDF"

    def transform(self, data_model: ConceptualDataModel) -> ConceptualDataModel:
        copy = data_model.model_copy(deep=True)
        copy.concepts = self._fix_concepts(copy.concepts)
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
    def _fix_concept(cls, concept: ConceptEntity) -> ConceptEntity:
        if isinstance(concept, ConceptEntity) and type(concept.prefix) is str:
            concept = ConceptEntity(
                prefix=cls._fix_entity(concept.prefix),
                suffix=cls._fix_entity(concept.suffix),
            )

        return concept

    @classmethod
    def _fix_value_type(
        cls, value_type: DataType | ConceptEntity | MultiValueTypeInfo
    ) -> DataType | ConceptEntity | MultiValueTypeInfo:
        fixed_value_type: DataType | ConceptEntity | MultiValueTypeInfo

        # value type specified as MultiValueTypeInfo
        if isinstance(value_type, MultiValueTypeInfo):
            fixed_value_type = MultiValueTypeInfo(
                types=[cast(DataType | ConceptEntity, cls._fix_value_type(type_)) for type_ in value_type.types],
            )

        # value type specified as ClassEntity instance
        elif isinstance(value_type, ConceptEntity):
            fixed_value_type = cls._fix_concept(value_type)

        # this is a DataType instance but also we should default to original value
        else:
            fixed_value_type = value_type

        return fixed_value_type

    @classmethod
    def _fix_concepts(cls, definitions: SheetList[Concept]) -> SheetList[Concept]:
        fixed_definitions = SheetList[Concept]()
        for definition in definitions:
            definition.concept = cls._fix_concept(definition.concept)
            fixed_definitions.append(definition)
        return fixed_definitions

    @classmethod
    def _fix_properties(cls, definitions: SheetList[ConceptualProperty]) -> SheetList[ConceptualProperty]:
        fixed_definitions = SheetList[ConceptualProperty]()
        for definition in definitions:
            definition.concept = cls._fix_concept(definition.concept)
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
    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel: ...

    @overload
    def transform(self, data_model: ConceptualDataModel) -> ConceptualDataModel: ...

    def transform(self, data_model: ConceptualDataModel | PhysicalDataModel) -> ConceptualDataModel | PhysicalDataModel:
        copy: ConceptualDataModel | PhysicalDataModel = data_model.model_copy(deep=True)

        # Case: Prefix Conceptual Data Model
        if isinstance(copy, ConceptualDataModel):
            # prefix classes
            for cls in copy.concepts:
                if cls.concept.prefix == copy.metadata.prefix:
                    cls.concept = self._with_prefix(cls.concept)

                if cls.implements:
                    # prefix parents
                    for i, parent_class in enumerate(cls.implements):
                        if parent_class.prefix == copy.metadata.prefix:
                            cls.implements[i] = self._with_prefix(parent_class)

            for prop in copy.properties:
                if prop.concept.prefix == copy.metadata.prefix:
                    prop.concept = self._with_prefix(prop.concept)

                # value type property is not multi and it is ClassEntity

                if isinstance(prop.value_type, ConceptEntity) and prop.value_type.prefix == copy.metadata.prefix:
                    prop.value_type = self._with_prefix(cast(ConceptEntity, prop.value_type))
                elif isinstance(prop.value_type, MultiValueTypeInfo):
                    for i, value_type in enumerate(prop.value_type.types):
                        if isinstance(value_type, ConceptEntity) and value_type.prefix == copy.metadata.prefix:
                            prop.value_type.types[i] = self._with_prefix(cast(ConceptEntity, value_type))
            return copy

        # Case: Prefix Physical Data Model
        elif isinstance(copy, PhysicalDataModel):
            for view in copy.views:
                if view.view.space == copy.metadata.space:
                    view.view = self._with_prefix(view.view)

                if view.implements:
                    for i, parent_view in enumerate(view.implements):
                        if parent_view.space == copy.metadata.space:
                            view.implements[i] = self._with_prefix(parent_view)

            for physical_prop in copy.properties:
                if physical_prop.view.space == copy.metadata.space:
                    physical_prop.view = self._with_prefix(physical_prop.view)

                if (
                    isinstance(physical_prop.value_type, ViewEntity)
                    and physical_prop.value_type.space == copy.metadata.space
                ):
                    physical_prop.value_type = self._with_prefix(physical_prop.value_type)

                if (
                    isinstance(physical_prop.container, ContainerEntity)
                    and physical_prop.container.space == copy.metadata.space
                ):
                    physical_prop.container = self._with_prefix(physical_prop.container)

            if copy.containers:
                for container in copy.containers:
                    if container.container.space == copy.metadata.space:
                        container.container = self._with_prefix(container.container)
            return copy

        raise NeatValueError(f"Unsupported data_model type: {type(copy)}")

    @overload
    def _with_prefix(self, entity: ConceptEntity) -> ConceptEntity: ...

    @overload
    def _with_prefix(self, entity: ViewEntity) -> ViewEntity: ...

    @overload
    def _with_prefix(self, entity: ContainerEntity) -> ContainerEntity: ...

    def _with_prefix(
        self, entity: ViewEntity | ContainerEntity | ConceptEntity
    ) -> ViewEntity | ContainerEntity | ConceptEntity:
        if isinstance(entity, ViewEntity | ContainerEntity | ConceptEntity):
            entity.suffix = f"{self._prefix}{entity.suffix}"

        else:
            raise NeatValueError(f"Unsupported entity type: {type(entity)}")

        return entity


class StandardizeNaming(ConversionTransformer):
    """Sets views/classes/container names to PascalCase and properties to camelCase."""

    @property
    def description(self) -> str:
        return "Sets views/classes/containers names to PascalCase and properties to camelCase."

    @overload
    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel: ...

    @overload
    def transform(self, data_model: ConceptualDataModel) -> ConceptualDataModel: ...

    def transform(self, data_model: ConceptualDataModel | PhysicalDataModel) -> ConceptualDataModel | PhysicalDataModel:
        output = data_model.model_copy(deep=True)
        if isinstance(output, ConceptualDataModel):
            return self._standardize_conceptual_data_model(output)
        elif isinstance(output, PhysicalDataModel):
            return self._standardize_physical_data_model(output)
        raise NeatValueError(f"Unsupported data_model type: {type(output)}")

    def _standardize_conceptual_data_model(self, data_model: ConceptualDataModel) -> ConceptualDataModel:
        new_by_old_concept_suffix: dict[str, str] = {}
        for cls in data_model.concepts:
            new_suffix = NamingStandardization.standardize_concept_str(cls.concept.suffix)
            new_by_old_concept_suffix[cls.concept.suffix] = new_suffix
            cls.concept.suffix = new_suffix

        for cls in data_model.concepts:
            if cls.implements:
                for i, parent in enumerate(cls.implements):
                    if parent.suffix in new_by_old_concept_suffix:
                        cls.implements[i].suffix = new_by_old_concept_suffix[parent.suffix]

        for prop in data_model.properties:
            prop.property_ = NamingStandardization.standardize_property_str(prop.property_)
            if prop.concept.suffix in new_by_old_concept_suffix:
                prop.concept.suffix = new_by_old_concept_suffix[prop.concept.suffix]

            if isinstance(prop.value_type, ConceptEntity) and prop.value_type.suffix in new_by_old_concept_suffix:
                prop.value_type.suffix = new_by_old_concept_suffix[prop.value_type.suffix]

            if isinstance(prop.value_type, MultiValueTypeInfo):
                for i, value_type in enumerate(prop.value_type.types):
                    if isinstance(value_type, ConceptEntity) and value_type.suffix in new_by_old_concept_suffix:
                        prop.value_type.types[i].suffix = new_by_old_concept_suffix[value_type.suffix]  # type: ignore[union-attr]

        return data_model

    def _standardize_physical_data_model(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        new_by_old_view: dict[str, str] = {}
        for view in data_model.views:
            new_suffix = NamingStandardization.standardize_concept_str(view.view.suffix)
            new_by_old_view[view.view.suffix] = new_suffix
            view.view.suffix = new_suffix
        new_by_old_container: dict[str, str] = {}
        if data_model.containers:
            for container in data_model.containers:
                new_suffix = NamingStandardization.standardize_concept_str(container.container.suffix)
                new_by_old_container[container.container.suffix] = new_suffix
                container.container.suffix = new_suffix

        for view in data_model.views:
            if view.implements:
                for i, parent in enumerate(view.implements):
                    if parent.suffix in new_by_old_view:
                        view.implements[i].suffix = new_by_old_view[parent.suffix]
            if view.filter_ and isinstance(view.filter_, HasDataFilter) and view.filter_.inner:
                for i, item in enumerate(view.filter_.inner):
                    if isinstance(item, ContainerEntity) and item.suffix in new_by_old_container:
                        view.filter_.inner[i].suffix = new_by_old_container[item.suffix]
                    if isinstance(item, ViewEntity) and item.suffix in new_by_old_view:
                        view.filter_.inner[i].suffix = new_by_old_view[item.suffix]
        if data_model.containers:
            for container in data_model.containers:
                if container.constraint:
                    for i, constraint in enumerate(container.constraint):
                        if constraint.suffix in new_by_old_container:
                            container.constraint[i].suffix = new_by_old_container[constraint.suffix]
        new_property_by_view_by_old_property: dict[ViewEntity, dict[str, str]] = defaultdict(dict)
        for prop in data_model.properties:
            if prop.view.suffix in new_by_old_view:
                prop.view.suffix = new_by_old_view[prop.view.suffix]
            new_view_property = NamingStandardization.standardize_property_str(prop.view_property)
            new_property_by_view_by_old_property[prop.view][prop.view_property] = new_view_property
            prop.view_property = new_view_property
            if isinstance(prop.value_type, ViewEntity) and prop.value_type.suffix in new_by_old_view:
                prop.value_type.suffix = new_by_old_view[prop.value_type.suffix]
            if (
                isinstance(prop.connection, EdgeEntity)
                and prop.connection.properties
                and prop.connection.properties.suffix in new_by_old_view
            ):
                prop.connection.properties.suffix = new_by_old_view[prop.connection.properties.suffix]
            if isinstance(prop.container, ContainerEntity) and prop.container.suffix in new_by_old_container:
                prop.container.suffix = new_by_old_container[prop.container.suffix]
            if prop.container_property:
                prop.container_property = NamingStandardization.standardize_property_str(prop.container_property)
        for prop in data_model.properties:
            if (
                isinstance(prop.connection, ReverseConnectionEntity)
                and isinstance(prop.value_type, ViewEntity)
                and prop.value_type in new_property_by_view_by_old_property
            ):
                new_by_old_property = new_property_by_view_by_old_property[prop.value_type]
                if prop.connection.property_ in new_by_old_property:
                    prop.connection.property_ = new_by_old_property[prop.connection.property_]
        return data_model


class ConceptualToPhysical(ConversionTransformer[ConceptualDataModel, PhysicalDataModel]):
    """Converts conceptual to physical data model."""

    def __init__(
        self,
        ignore_undefined_value_types: bool = False,
        reserved_properties: Literal["error", "warning"] = "error",
        client: NeatClient | None = None,
    ):
        self.ignore_undefined_value_types = ignore_undefined_value_types
        self.reserved_properties = reserved_properties
        self.client = client

    def transform(self, data_model: ConceptualDataModel) -> PhysicalDataModel:
        return _ConceptualDataModelConverter(data_model, self.client).as_physical_data_model(
            self.ignore_undefined_value_types, self.reserved_properties
        )


class PhysicalToConceptual(ConversionTransformer[PhysicalDataModel, ConceptualDataModel]):
    """Converts Physical to Conceptual data model."""

    def __init__(self, instance_namespace: Namespace | None = None):
        self.instance_namespace = instance_namespace

    def transform(self, data_model: PhysicalDataModel) -> ConceptualDataModel:
        return _PhysicalDataModelConverter(data_model, self.instance_namespace).as_conceptual_data_model()


class ConvertToDataModel(ConversionTransformer[VerifiedDataModel, VerifiedDataModel]):
    """Converts any data_model to any data_model."""

    def __init__(self, out_cls: type[VerifiedDataModel]):
        self._out_cls = out_cls

    def transform(self, data_model: VerifiedDataModel) -> VerifiedDataModel:
        if isinstance(data_model, self._out_cls):
            return data_model
        if isinstance(data_model, ConceptualDataModel) and self._out_cls is PhysicalDataModel:
            return ConceptualToPhysical().transform(data_model)
        if isinstance(data_model, PhysicalDataModel) and self._out_cls is ConceptualDataModel:
            return PhysicalToConceptual().transform(data_model)
        raise ValueError(f"Unsupported conversion from {type(data_model)} to {self._out_cls}")


_T_Entity = TypeVar("_T_Entity", bound=ConceptEntity | ViewEntity)


class SetIDDMSModel(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel]):
    def __init__(self, new_id: DataModelId | tuple[str, str, str], name: str | None = None):
        self.new_id = DataModelId.load(new_id)
        self.name = name

    @property
    def description(self) -> str:
        return f"Sets the Data Model ID to {self.new_id.as_tuple()}"

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        if self.new_id.version is None:
            raise NeatValueError("Version is required when setting a new Data Model ID")
        dump = data_model.dump()
        dump["metadata"]["space"] = self.new_id.space
        dump["metadata"]["external_id"] = self.new_id.external_id
        dump["metadata"]["version"] = self.new_id.version
        dump["metadata"]["name"] = self.name or self._generate_name()
        # Serialize and deserialize to set the new space and external_id
        # as the default values for the new model.
        return PhysicalDataModel.model_validate(UnverifiedPhysicalDataModel.load(dump).dump())

    def _generate_name(self) -> str:
        return title(to_words(self.new_id.external_id))


class ToExtensionModel(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel], ABC):
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

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        return self._to_enterprise(data_model)

    def _to_enterprise(self, reference_model: PhysicalDataModel) -> PhysicalDataModel:
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
        enterprise_containers.sort(key=lambda container: (container.container.space, container.container.external_id))
        enterprise_model.containers = enterprise_containers
        enterprise_properties.sort(
            key=lambda prop: (prop.view.space, prop.view.external_id, prop.view.version, prop.view_property)
        )
        enterprise_model.properties = enterprise_properties

        # Sorting all your views first.
        enterprise_model.views.sort(
            key=lambda view: (
                # Sorting your views first
                int(view.view.space != self.new_model_id.space),
                view.view.space,
                view.view.external_id,
                view.view.version,
            )
        )
        return enterprise_model

    @staticmethod
    def _create_connection_properties(
        data_model: PhysicalDataModel, new_views: SheetList[PhysicalView]
    ) -> SheetList[PhysicalProperty]:
        """Creates a new connection property for each connection property in the reference model.

        This is for example when you create an enterprise model from CogniteCore, you ensure that your
        new Asset, Equipment, TimeSeries, Activity, and File views all point to each other.
        """
        # Note all new news have an implements attribute that points to the original view
        previous_by_new_view = {view.implements[0]: view.view for view in new_views if view.implements}
        connection_properties = SheetList[PhysicalProperty]()
        for prop in data_model.properties:
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
        self, data_model: PhysicalDataModel
    ) -> tuple[
        SheetList[PhysicalView],
        SheetList[PhysicalContainer],
        SheetList[PhysicalProperty],
    ]:
        """Creates new views for the new model.

        If the dummy property is provided, it will also create a new container for each view
        with a single property that is the dummy property.
        """
        new_views = SheetList[PhysicalView]()
        new_containers = SheetList[PhysicalContainer]()
        new_properties = SheetList[PhysicalProperty]()

        for definition in data_model.views:
            view_entity = self._remove_cognite_affix(definition.view)
            view_entity.version = cast(str, self.new_model_id.version)
            view_entity.prefix = self.new_model_id.space
            new_views.append(
                PhysicalView(
                    view=view_entity,
                    implements=[definition.view],
                    in_model=True,
                    name=definition.name,
                )
            )

            if self.dummy_property is None:
                continue

            container_entity = ContainerEntity(space=view_entity.prefix, externalId=view_entity.external_id)

            container = PhysicalContainer(container=container_entity)

            property_id = f"{to_camel_case(view_entity.suffix)}{self.dummy_property}"
            property_ = PhysicalProperty(
                view=view_entity,
                view_property=property_id,
                value_type=String(),
                min_count=0,
                immutable=False,
                max_count=1,
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

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        reference_model = data_model
        reference_model_id = reference_model.metadata.as_data_model_id()
        if reference_model_id in COGNITE_MODELS:
            warnings.warn(
                SolutionModelBuildOnTopOfCDMWarning(reference_model_id=reference_model_id),
                stacklevel=2,
            )
        return self._to_solution(reference_model)

    def _to_solution(self, reference_data_model: PhysicalDataModel) -> PhysicalDataModel:
        """For creation of solution data model / data_model specifically for mapping over existing containers."""
        reference_data_model = self._expand_properties(reference_data_model.model_copy(deep=True))

        new_views, new_properties, read_view_by_new_view = self._create_views(reference_data_model)
        new_containers, new_container_properties = self._create_containers_update_view_filter(
            new_views, reference_data_model, read_view_by_new_view
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

        metadata = reference_data_model.metadata.model_copy(
            deep=True,
            update={
                "space": self.new_model_id.space,
                "external_id": self.new_model_id.external_id,
                "version": self.new_model_id.version,
                "name": f"{self.type_} data model",
            },
        )
        return PhysicalDataModel(
            metadata=metadata,
            properties=new_properties,
            views=new_views,
            containers=new_containers or None,
            enum=reference_data_model.enum,
            nodes=reference_data_model.nodes,
        )

    @staticmethod
    def _expand_properties(data_model: PhysicalDataModel) -> PhysicalDataModel:
        probe = DataModelAnalysis(physical=data_model)
        ancestor_properties_by_view = probe.properties_by_view(
            include_ancestors=True,
            include_different_space=True,
        )
        property_ids_by_view = {
            view: {prop.view_property for prop in properties}
            for view, properties in probe.properties_by_view(
                include_ancestors=False, include_different_space=True
            ).items()
        }
        for view, property_ids in property_ids_by_view.items():
            ancestor_properties = ancestor_properties_by_view.get(view, [])
            for prop in ancestor_properties:
                if isinstance(prop.connection, ReverseConnectionEntity):
                    # If you try to add a reverse direct relation of a parent, it will fail as the ValueType of the
                    # original property will point to the parent view, and not the child.
                    continue
                if prop.view_property not in property_ids:
                    data_model.properties.append(prop)
                    property_ids.add(prop.view_property)
        return data_model

    def _create_views(
        self, reference: PhysicalDataModel
    ) -> tuple[
        SheetList[PhysicalView],
        SheetList[PhysicalProperty],
        dict[ViewEntity, ViewEntity],
    ]:
        renaming: dict[ViewEntity, ViewEntity] = {}
        new_views = SheetList[PhysicalView]()
        read_view_by_new_view: dict[ViewEntity, ViewEntity] = {}
        for ref_view in reference.views:
            if (self.skip_cognite_views and ref_view.view.space in COGNITE_SPACES) or (
                self.exclude_views_in_other_spaces and ref_view.view.space != reference.metadata.space
            ):
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
                new_view = PhysicalView(
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

        new_properties = SheetList[PhysicalProperty]()
        new_view_entities = {view.view for view in new_views}
        for prop in reference.properties:
            new_property = prop.model_copy(deep=True)
            if new_property.value_type in renaming and isinstance(new_property.value_type, ViewEntity):
                new_property.value_type = renaming[new_property.value_type]
            if new_property.view in renaming:
                new_property.view = renaming[new_property.view]
            if new_property.view in new_view_entities and (
                not isinstance(new_property.value_type, ViewEntity) or new_property.value_type in new_view_entities
            ):
                new_properties.append(new_property)
        return new_views, new_properties, read_view_by_new_view

    def _create_containers_update_view_filter(
        self,
        new_views: SheetList[PhysicalView],
        reference: PhysicalDataModel,
        read_view_by_new_view: dict[ViewEntity, ViewEntity],
    ) -> tuple[SheetList[PhysicalContainer], SheetList[PhysicalProperty]]:
        new_containers = SheetList[PhysicalContainer]()
        container_properties: SheetList[PhysicalProperty] = SheetList[PhysicalProperty]()
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
                prefix = to_camel_case(view.view.suffix)
                if self.properties == "repeat" and self.dummy_property:
                    property_ = PhysicalProperty(
                        view=view.view,
                        view_property=f"{prefix}{self.dummy_property}",
                        value_type=String(),
                        min_count=0,
                        max_count=1,
                        immutable=False,
                        container=container_entity,
                        container_property=f"{prefix}{self.dummy_property}",
                    )
                    new_containers.append(PhysicalContainer(container=container_entity))
                    container_properties.append(property_)
                elif self.properties == "repeat" and self.dummy_property is None:
                    # For this case we set the filter. This is used by the DataProductModel.
                    # Inherit view filter from original model to ensure the same instances are returned
                    # when querying the new view.
                    if ref_view := ref_views_by_external_id.get(view.view.external_id):
                        self._set_view_filter(view, ref_containers_by_ref_view, ref_view)
                elif self.properties == "connection" and self.direct_property:
                    property_ = PhysicalProperty(
                        view=view.view,
                        view_property=self.direct_property,
                        value_type=read_view,
                        min_count=0,
                        max_count=1,
                        immutable=False,
                        container=container_entity,
                        container_property=self.direct_property,
                        connection="direct",
                    )
                    new_containers.append(PhysicalContainer(container=container_entity))
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
        self,
        view: PhysicalView,
        ref_containers_by_ref_view: dict[ViewEntity, set[ContainerEntity]],
        ref_view: PhysicalView,
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

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        # Overwrite transform to avoid the warning.
        return self._to_solution(data_model)


class DropModelViews(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel]):
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

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        exclude_views: set[ViewEntity] = {
            view.view for view in data_model.views if view.view.suffix in self.drop_external_ids
        }
        if data_model.metadata.as_data_model_id() in COGNITE_MODELS:
            exclude_views |= {
                ViewEntity.from_id(view_id, "v1")
                for collection in self.drop_collection
                for view_id in self._VIEW_BY_COLLECTION[collection]
            }
        new_model = data_model.model_copy(deep=True)

        properties_by_view = DataModelAnalysis(physical=new_model).properties_by_view(include_ancestors=True)

        new_model.views = SheetList[PhysicalView]([view for view in new_model.views if view.view not in exclude_views])
        new_properties = SheetList[PhysicalProperty]()
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
            SheetList[PhysicalContainer](
                [container for container in new_model.containers or [] if container.container in mapped_containers]
            )
            or None
        )

        return new_model

    @classmethod
    def _is_asset_3D_property(cls, prop: PhysicalProperty) -> bool:
        return prop.view.as_id() == cls._ASSET_VIEW and prop.view_property == "object3D"

    @property
    def description(self) -> str:
        return f"Removed {len(self.drop_external_ids) + len(self.drop_collection)} views from data model"


class IncludeReferenced(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel]):
    def __init__(self, client: NeatClient, include_properties: bool = False) -> None:
        self._client = client
        self.include_properties = include_properties

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        physical_data_model = data_model
        view_ids, container_ids = PhysicalValidation(physical_data_model).imported_views_and_containers_ids()
        if not (view_ids or container_ids):
            warnings.warn(
                NeatValueWarning(
                    f"Data model {physical_data_model.metadata.as_data_model_id()} does not have any "
                    "referenced views or containers."
                    "that is not already included in the data model."
                ),
                stacklevel=2,
            )
            return physical_data_model

        schema = self._client.schema.retrieve([v.as_id() for v in view_ids], [c.as_id() for c in container_ids])
        copy_ = physical_data_model.model_copy(deep=True)
        # Sorting to ensure deterministic order
        schema.containers = ContainerApplyDict(sorted(schema.containers.items(), key=lambda x: x[0].as_tuple()))
        schema.views = ViewApplyDict(sorted(schema.views.items(), key=lambda x: x[0].as_tuple()))
        importer = DMSImporter(schema)

        imported = importer.to_data_model()
        if imported.unverified_data_model is None:
            raise NeatValueError("Could not import the referenced views and containers.")

        verified = VerifyPhysicalDataModel(validate=False).transform(imported)
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


class AddConceptImplements(VerifiedDataModelTransformer[ConceptualDataModel, ConceptualDataModel]):
    def __init__(self, implements: str, suffix: str):
        self.implements = implements
        self.suffix = suffix

    def transform(self, data_model: ConceptualDataModel) -> ConceptualDataModel:
        output = data_model.model_copy(deep=True)
        for concept in output.concepts:
            if concept.concept.suffix.endswith(self.suffix):
                concept.implements = [ConceptEntity(prefix=concept.concept.prefix, suffix=self.implements)]
        return output

    @property
    def description(self) -> str:
        return f"Added implements property to classes with suffix {self.suffix}"


class ClassicPrepareCore(VerifiedDataModelTransformer[ConceptualDataModel, ConceptualDataModel]):
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

    def transform(self, data_model: ConceptualDataModel) -> ConceptualDataModel:
        output = data_model.model_copy(deep=True)
        for prop in output.properties:
            if prop.concept.suffix == "Timeseries" and prop.property_ == "isString":
                prop.value_type = String()
        prefix = output.metadata.prefix
        namespace = output.metadata.namespace
        source_system_class = Concept(
            concept=ConceptEntity(prefix=prefix, suffix="ClassicSourceSystem"),
            description="A source system that provides data to the data model.",
            neatId=namespace["ClassicSourceSystem"],
            instance_source=self.instance_namespace["ClassicSourceSystem"],
        )
        output.concepts.append(source_system_class)
        for prop in output.properties:
            if prop.property_ == "source" and prop.concept.suffix != "ClassicSourceSystem":
                prop.value_type = ConceptEntity(prefix=prefix, suffix="ClassicSourceSystem")
            elif prop.property_ == "externalId":
                prop.property_ = "classicExternalId"
                if self.reference_timeseries and prop.concept.suffix == "ClassicTimeSeries":
                    prop.value_type = Timeseries()
                elif self.reference_files and prop.concept.suffix == "ClassicFile":
                    prop.value_type = File()
            elif prop.property_ == "sourceExternalId" and prop.concept.suffix == "ClassicRelationship":
                prop.property_ = "startNode"
            elif prop.property_ == "targetExternalId" and prop.concept.suffix == "ClassicRelationship":
                prop.property_ = "endNode"
        instance_prefix = next(
            (prefix for prefix, namespace in output.prefixes.items() if namespace == self.instance_namespace), None
        )
        if instance_prefix is None:
            raise NeatValueError("Instance namespace not found in the prefixes.")

        output.properties.append(
            ConceptualProperty(
                neatId=namespace["ClassicSourceSystem/name"],
                property_="name",
                value_type=String(),
                concept=ConceptEntity(prefix=prefix, suffix="ClassicSourceSystem"),
                max_count=1,
                instance_source=[self.instance_namespace["name"]],
            )
        )
        return output


class ChangeViewPrefix(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel]):
    def __init__(self, old: str, new: str) -> None:
        self.old = old
        self.new = new

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        output = data_model.model_copy(deep=True)
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


class MergePhysicalDataModels(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel]):
    def __init__(self, extra: PhysicalDataModel) -> None:
        self.extra = extra

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        output = data_model.model_copy(deep=True)
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
                    output.containers = SheetList[PhysicalContainer]()
                output.containers.append(new_containers_by_entity[prop.container])
            if isinstance(prop.value_type, Enum) and prop.value_type.collection not in existing_enum_collections:
                if output.enum is None:
                    output.enum = SheetList[PhysicalEnum]()
                output.enum.append(new_enum_collections_by_entity[prop.value_type.collection])

        existing_nodes = {node.node for node in output.nodes or []}
        for node in self.extra.nodes or []:
            if node.node not in existing_nodes:
                if output.nodes is None:
                    output.nodes = SheetList[PhysicalNodeType]()
                output.nodes.append(node)

        return output

    @property
    def description(self) -> str:
        return f"Merged with {self.extra.metadata.as_data_model_id()}"


class MergeConceptualDataModels(VerifiedDataModelTransformer[ConceptualDataModel, ConceptualDataModel]):
    def __init__(self, extra: ConceptualDataModel) -> None:
        self.extra = extra

    def transform(self, data_model: ConceptualDataModel) -> ConceptualDataModel:
        output = data_model.model_copy(deep=True)
        existing_classes = {cls.concept for cls in output.concepts}
        for cls in self.extra.concepts:
            if cls.concept not in existing_classes:
                output.concepts.append(cls)
        existing_properties = {(prop.concept, prop.property_) for prop in output.properties}
        for prop in self.extra.properties:
            if (prop.concept, prop.property_) not in existing_properties:
                output.properties.append(prop)
        for prefix, namespace in self.extra.prefixes.items():
            if prefix not in output.prefixes:
                output.prefixes[prefix] = namespace
        return output


class _ConceptualDataModelConverter:
    _start_or_end_node: ClassVar[frozenset[str]] = frozenset({"endNode", "end_node", "startNode", "start_node"})

    def __init__(
        self,
        conceptual_data_model: ConceptualDataModel,
        client: NeatClient | None = None,
    ):
        self.conceptual_data_model = conceptual_data_model
        self.property_count_by_container: dict[ContainerEntity, int] = defaultdict(int)
        self.client = client

    def as_physical_data_model(
        self,
        ignore_undefined_value_types: bool = False,
        reserved_properties: Literal["error", "warning"] = "error",
    ) -> "PhysicalDataModel":
        from cognite.neat.v0.core._data_model.models.physical._verified import (
            PhysicalContainer,
            PhysicalDataModel,
            PhysicalProperty,
            PhysicalView,
        )

        conceptual_metadata = self.conceptual_data_model.metadata
        default_version = conceptual_metadata.version
        default_space = self._to_space(conceptual_metadata.prefix)
        physical_metadata = self._convert_conceptual_to_physical_metadata(conceptual_metadata)

        properties_by_concept: dict[ConceptEntity, set[str]] = defaultdict(set)
        for prop in self.conceptual_data_model.properties:
            properties_by_concept[prop.concept].add(prop.property_)

        # Edge Classes is defined by having both startNode and endNode properties
        edge_classes = {
            concept
            for concept, concept_properties in properties_by_concept.items()
            if ({"startNode", "start_node"} & concept_properties) and ({"endNode", "end_node"} & concept_properties)
        }
        edge_value_types_by_concept_property_pair = {
            (prop.concept, prop.property_): prop.value_type
            for prop in self.conceptual_data_model.properties
            if prop.value_type in edge_classes and isinstance(prop.value_type, ConceptEntity)
        }
        end_node_by_edge = {
            prop.concept: prop.value_type
            for prop in self.conceptual_data_model.properties
            if prop.concept in edge_classes
            and (prop.property_ == "endNode" or prop.property_ == "end_node")
            and isinstance(prop.value_type, ConceptEntity)
        }
        ancestors_by_view: dict[ViewEntity, set[ViewEntity]] = {}
        parents_by_concept = DataModelAnalysis(self.conceptual_data_model).parents_by_concept(
            include_ancestors=True, include_different_space=True
        )
        for concept, parents in parents_by_concept.items():
            view_type = concept.as_view_entity(default_space, default_version)
            parent_views = {parent.as_view_entity(default_space, default_version) for parent in parents}
            if view_type in ancestors_by_view:
                ancestors_by_view[view_type].update(parent_views)
            else:
                ancestors_by_view[view_type] = parent_views

        cognite_properties, cognite_containers, cognite_views = self._get_cognite_components()
        for view in cognite_views:
            if view in ancestors_by_view:
                ancestors_by_view[view].update(cognite_views[view])
            else:
                ancestors_by_view[view] = cognite_views[view]

        properties_by_concept: dict[ConceptEntity, list[PhysicalProperty]] = defaultdict(list)
        used_containers: dict[ContainerEntity, Counter[ConceptEntity]] = defaultdict(Counter)
        used_cognite_containers: dict[ContainerEntity, PhysicalContainer] = {}

        for prop in self.conceptual_data_model.properties:
            if ignore_undefined_value_types and isinstance(prop.value_type, UnknownEntity):
                continue
            if prop.concept in edge_classes and prop.property_ in self._start_or_end_node:
                continue
            if prop.property_ in DMS_RESERVED_PROPERTIES:
                msg = f"Property {prop.property_} is a reserved property in DMS."
                if reserved_properties == "error":
                    raise NeatValueError(msg)
                warnings.warn(NeatValueWarning(f"{msg} Skipping..."), stacklevel=2)
                continue

            if cognite_property := self._find_cognite_property(
                prop.property_, parents_by_concept[prop.concept], cognite_properties
            ):
                physical_property = self._customize_physical_property(
                    prop,
                    cognite_property,
                    prop.concept,
                    default_space,
                    default_version,
                    ancestors_by_view,
                )
                if physical_property.container:
                    if physical_property.container not in used_cognite_containers:
                        used_cognite_containers[physical_property.container] = cognite_containers[
                            physical_property.container
                        ]
            else:
                # Not matching any parent.
                physical_property = self._as_physical_property(
                    prop,
                    default_space,
                    default_version,
                    edge_classes,
                    edge_value_types_by_concept_property_pair,
                    end_node_by_edge,
                )
                if physical_property.container:
                    used_containers[physical_property.container][prop.concept] += 1

            properties_by_concept[prop.concept].append(physical_property)

        views: list[PhysicalView] = []

        for concept in self.conceptual_data_model.concepts:
            physical_view = PhysicalView(
                name=concept.name,
                view=concept.concept.as_view_entity(default_space, default_version),
                description=concept.description,
                implements=self._get_view_implements(concept, conceptual_metadata),
            )

            physical_view.conceptual = concept.neatId
            views.append(physical_view)

        concept_by_concept_entity = {cls_.concept: cls_ for cls_ in self.conceptual_data_model.concepts}

        existing_containers: set[ContainerEntity] = set()

        containers: list[PhysicalContainer] = []
        for container_entity, concept_entities in used_containers.items():
            if container_entity in existing_containers:
                continue
            constrains = self._create_container_constraint(
                concept_entities,
                default_space,
                concept_by_concept_entity,
                used_containers,
            )
            most_used_concept_entity = concept_entities.most_common(1)[0][0]
            concept = concept_by_concept_entity[most_used_concept_entity]

            if len(set(concept_entities) - set(edge_classes)) == 0:
                used_for: Literal["node", "edge", "all"] = "edge"
            elif len(set(concept_entities) - set(edge_classes)) == len(concept_entities):
                used_for = "node"
            else:
                used_for = "all"

            container = PhysicalContainer(
                container=container_entity,
                name=concept.name,
                description=concept.description,
                constraint=constrains or None,
                used_for=used_for,
            )
            containers.append(container)

        if used_cognite_containers:
            containers.extend(used_cognite_containers.values())

        physical_data_model = PhysicalDataModel(
            metadata=physical_metadata,
            properties=SheetList[PhysicalProperty](
                [prop for prop_set in properties_by_concept.values() for prop in prop_set]
            ),
            views=SheetList[PhysicalView](views),
            containers=SheetList[PhysicalContainer](containers),
        )

        self.conceptual_data_model.sync_with_physical_data_model(physical_data_model)

        return physical_data_model

    def _get_cognite_components(
        self,
    ) -> tuple[
        dict[tuple[ConceptEntity, str], PhysicalProperty],
        dict[ContainerEntity, PhysicalContainer],
        dict[ViewEntity, set[ViewEntity]],
    ]:
        cognite_concepts = self._get_cognite_concepts()
        cognite_properties: dict[tuple[ConceptEntity, str], PhysicalProperty] = {}
        cognite_containers: dict[ContainerEntity, PhysicalContainer] = {}
        cognite_views: dict[ViewEntity, set[ViewEntity]] = {}
        if cognite_concepts:
            if self.client is None:
                raise CDFMissingClientError(
                    f"Cannot convert {self.conceptual_data_model.metadata.as_data_model_id()}. Missing Cognite Client."
                    f"This is required as the data model is referencing cognite concepts in the implements"
                    f"{humanize_collection(cognite_concepts)}"
                )
            cognite_data_model = self._get_cognite_physical_data_model(cognite_concepts, self.client)

            cognite_properties = {
                (
                    physical_property.view.as_concept_entity(),
                    physical_property.view_property,
                ): physical_property
                for physical_property in cognite_data_model.properties
            }
            cognite_containers = {container.container: container for container in cognite_data_model.containers or []}
            cognite_views = DataModelAnalysis(physical=cognite_data_model).implements_by_view(
                include_ancestors=True, include_different_space=True
            )
        return cognite_properties, cognite_containers, cognite_views

    @staticmethod
    def _create_container_constraint(
        concept_entities: Counter[ConceptEntity],
        default_space: str,
        concept_by_concept_entity: dict[ConceptEntity, Concept],
        referenced_containers: Collection[ContainerEntity],
    ) -> list[ContainerConstraintEntity]:
        constrains: list[ContainerConstraintEntity] = []
        for entity in concept_entities:
            concept = concept_by_concept_entity[entity]
            for parent in concept.implements or []:
                parent_entity = parent.as_container_entity(default_space)
                if parent_entity in referenced_containers:
                    constrains.append(
                        ContainerConstraintEntity(
                            prefix="requires",
                            suffix=f"{parent_entity.space}_{parent_entity.external_id}"[:CONSTRAINT_ID_MAX_LENGTH],
                            require=parent_entity,
                        )
                    )
        return constrains

    @classmethod
    def _convert_conceptual_to_physical_metadata(cls, metadata: ConceptualMetadata) -> "PhysicalMetadata":
        from cognite.neat.v0.core._data_model.models.physical._verified import (
            PhysicalMetadata,
        )

        physical_metadata = PhysicalMetadata(
            space=metadata.space,
            version=metadata.version,
            external_id=metadata.external_id,
            creator=metadata.creator,
            name=metadata.name,
            created=metadata.created,
            updated=metadata.updated,
        )

        physical_metadata.conceptual = metadata.identifier
        return physical_metadata

    def _as_physical_property(
        self,
        conceptual_property: ConceptualProperty,
        default_space: str,
        default_version: str,
        edge_classes: set[ConceptEntity],
        edge_value_types_by_concept_property_pair: dict[tuple[ConceptEntity, str], ConceptEntity],
        end_node_by_edge: dict[ConceptEntity, ConceptEntity],
    ) -> "PhysicalProperty":
        from cognite.neat.v0.core._data_model.models.physical._verified import PhysicalProperty

        # returns property type, which can be ObjectProperty or DatatypeProperty
        value_type = self._get_value_type(
            conceptual_property,
            default_space,
            default_version,
            edge_classes,
            end_node_by_edge,
        )

        connection = self._get_connection(
            conceptual_property,
            value_type,
            edge_value_types_by_concept_property_pair,
            default_space,
            default_version,
        )

        container: ContainerEntity | None = None
        container_property: str | None = None
        # DMS should have min count of either 0 or 1
        min_count = min(1, max(0, conceptual_property.min_count or 0))
        max_count = conceptual_property.max_count
        if isinstance(connection, EdgeEntity):
            min_count = 0
            max_count = 1 if max_count == 1 else float("inf")
        elif isinstance(connection, ReverseConnectionEntity):
            min_count = 0
            max_count = 1 if max_count == 1 else float("inf")
        elif connection == "direct":
            min_count = 0
            container, container_property = self._get_container(conceptual_property, default_space)
        else:
            container, container_property = self._get_container(conceptual_property, default_space)

        physical_property = PhysicalProperty(
            name=conceptual_property.name,
            value_type=value_type,
            min_count=min_count,
            max_count=max_count,
            connection=connection,
            default=conceptual_property.default,
            container=container,
            container_property=container_property,
            view=conceptual_property.concept.as_view_entity(default_space, default_version),
            view_property=conceptual_property.property_,
        )

        # linking
        physical_property.conceptual = conceptual_property.neatId

        return physical_property

    @staticmethod
    def _customize_physical_property(
        conceptual_property: ConceptualProperty,
        physical_property: PhysicalProperty,
        concept: ConceptEntity,
        default_space: str,
        default_version: str,
        ancestors_by_view: dict[ViewEntity, set[ViewEntity]],
    ) -> PhysicalProperty:
        """Customize the physical property to match the conceptual property.
        This means updating the name and description of the physical property with the conceptual property.
        In addition, the value type can be updated given that the value type is matches the physical property value
        type or in the case of a View Value type a derivative of the cognite property value type.

        Args:
            prop: Information property
            cognite_prop: Cognite property
            concept: Concept entity
            default_space: The default space
            default_version: The default version
            ancestors_by_view: Ancestors by view

        Returns:
            PhysicalProperty: The customized physical property

        """
        value_type: DataType | ViewEntity | PhysicalUnknownEntity = physical_property.value_type
        if isinstance(conceptual_property.value_type, DataType) and conceptual_property.value_type != value_type:
            warnings.warn(
                PropertyOverwritingWarning(
                    conceptual_property.property_,
                    "property",
                    "value type",
                    (str(conceptual_property.value_type),),
                ),
                stacklevel=2,
            )
        elif isinstance(conceptual_property.value_type, DataType):
            # User set the same value type as core concept.
            pass
        elif isinstance(conceptual_property.value_type, ConceptEntity) and isinstance(
            physical_property.value_type, ViewEntity
        ):
            view_type = conceptual_property.value_type.as_view_entity(default_space, default_version)
            ancestors = ancestors_by_view.get(view_type, set())
            if view_type == physical_property.value_type or physical_property.value_type in ancestors:
                value_type = view_type
            else:
                warnings.warn(
                    NeatValueWarning(
                        f"Invalid Value Type. The view {view_type} must implement "
                        f"{humanize_collection(ancestors, bind_word='or')} "
                        "to be used as the Value Type in the "
                        f"{conceptual_property.concept!s}.{conceptual_property.property_}. "
                        f"Skipping..."
                    ),
                    stacklevel=2,
                )
        else:
            warnings.warn(
                NeatValueWarning(
                    f"Invalid Value Type. The {conceptual_property.value_type} is "
                    f"not supported as {conceptual_property.concept} implements"
                    "a cognite concepts. Will skip this, and use "
                    f"the {physical_property.value_type} instead."
                ),
                stacklevel=2,
            )

        return physical_property.model_copy(
            update={
                "view": concept.as_view_entity(default_space, default_version),
                "name": conceptual_property.name or physical_property.name,
                "description": conceptual_property.description or physical_property.description,
                "value_type": value_type,
            }
        )

    @staticmethod
    def _get_connection(
        conceptual_property: ConceptualProperty,
        value_type: DataType | ViewEntity | PhysicalUnknownEntity,
        edge_value_types_by_concept_property_pair: dict[tuple[ConceptEntity, str], ConceptEntity],
        default_space: str,
        default_version: str,
    ) -> Literal["direct"] | ReverseConnectionEntity | EdgeEntity | None:
        if (
            isinstance(value_type, ViewEntity)
            and (conceptual_property.concept, conceptual_property.property_)
            in edge_value_types_by_concept_property_pair
        ):
            edge_value_type = edge_value_types_by_concept_property_pair[
                (conceptual_property.concept, conceptual_property.property_)
            ]
            return EdgeEntity(properties=edge_value_type.as_view_entity(default_space, default_version))
        if isinstance(value_type, ViewEntity) and (
            conceptual_property.max_count in {float("inf"), None}
            or (isinstance(conceptual_property.max_count, int | float) and conceptual_property.max_count > 1)
        ):
            return EdgeEntity()
        elif isinstance(value_type, ViewEntity):
            return "direct"
        # defaulting to direct connection
        elif isinstance(value_type, PhysicalUnknownEntity):
            return "direct"
        return None

    def _get_value_type(
        self,
        conceptual_property: ConceptualProperty,
        default_space: str,
        default_version: str,
        edge_classes: set[ConceptEntity],
        end_node_by_edge: dict[ConceptEntity, ConceptEntity],
    ) -> DataType | ViewEntity | PhysicalUnknownEntity:
        if isinstance(conceptual_property.value_type, DataType):
            return conceptual_property.value_type

        # UnknownEntity should  resolve to DMSUnknownEntity
        # meaning end node type is unknown
        elif isinstance(conceptual_property.value_type, UnknownEntity):
            return PhysicalUnknownEntity()

        elif isinstance(conceptual_property.value_type, ConceptEntity) and (
            conceptual_property.value_type in edge_classes
        ):
            if conceptual_property.value_type in end_node_by_edge:
                return end_node_by_edge[conceptual_property.value_type].as_view_entity(default_space, default_version)
            # This occurs if the end node is not pointing to a class
            warnings.warn(
                NeatValueWarning(
                    f"Edge class {conceptual_property.value_type} does not "
                    "have 'endNode' property, defaulting to DMSUnknownEntity"
                ),
                stacklevel=2,
            )
            return PhysicalUnknownEntity()
        elif isinstance(conceptual_property.value_type, ConceptEntity):
            return conceptual_property.value_type.as_view_entity(default_space, default_version)

        elif isinstance(conceptual_property.value_type, MultiValueTypeInfo):
            # Multi Object type should resolve to DMSUnknownEntity
            # meaning end node type is unknown
            if conceptual_property.value_type.is_multi_object_type():
                non_unknown = [
                    type_ for type_ in conceptual_property.value_type.types if isinstance(type_, UnknownEntity)
                ]
                if list(non_unknown) == 1:
                    #
                    return non_unknown[0].as_view_entity(default_space, default_version)
                return PhysicalUnknownEntity()

            # Multi Data type should resolve to a single data type, or it should
            elif conceptual_property.value_type.is_multi_data_type():
                return self.convert_multi_data_type(conceptual_property.value_type)

            # Mixed types default to string
            else:
                non_any_uri = [type_ for type_ in conceptual_property.value_type.types if type_ != AnyURI()]
                if list(non_any_uri) == 1:
                    if isinstance(non_any_uri[0], ConceptEntity):
                        return non_any_uri[0].as_view_entity(default_space, default_version)
                    else:
                        return non_any_uri[0]
                return String()

        raise ValueError(f"Unsupported value type: {conceptual_property.value_type.type_}")

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

    def _get_container(self, prop: ConceptualProperty, default_space: str) -> tuple[ContainerEntity, str]:
        container_entity = prop.concept.as_container_entity(default_space)

        while self.property_count_by_container[container_entity] >= DMS_CONTAINER_PROPERTY_SIZE_LIMIT:
            container_entity.suffix = self._bump_suffix(container_entity.suffix)

        self.property_count_by_container[container_entity] += 1
        return container_entity, prop.property_

    def _get_view_implements(self, cls_: Concept, metadata: ConceptualMetadata) -> list[ViewEntity]:
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

    def _get_cognite_concepts(self) -> set[ConceptEntity]:
        return {
            cls_.concept for cls_ in self.conceptual_data_model.concepts if str(cls_.concept.prefix) in COGNITE_SPACES
        } | {
            parent
            for cls_ in self.conceptual_data_model.concepts
            for parent in cls_.implements or []
            if str(parent.prefix) in COGNITE_SPACES
        }

    @staticmethod
    def _get_cognite_physical_data_model(concepts: set[ConceptEntity], client: NeatClient) -> PhysicalDataModel:
        view_ids = [dm.ViewId(str(cls_.prefix), cls_.suffix, cls_.version) for cls_ in concepts]
        views = client.loaders.views.retrieve(view_ids, format="read", include_connected=True, include_ancestor=True)
        spaces = Counter(view.space for view in views)
        space = spaces.most_common(1)[0][0]
        model: dm.DataModel[dm.View] = dm.DataModel(
            space=space,
            external_id="CognitePlaceholderModel",
            version="v1",
            is_global=False,
            last_updated_time=1,
            created_time=1,
            name=None,
            description="This model is constructed to hold all properties/views/containers that are referenced"
            "by the data model being converted to DMS. This model is not meant to be used for any other"
            "purpose.",
            views=list(views),
        )
        unverified = DMSImporter.from_data_model(client, model).to_data_model()
        if unverified.unverified_data_model is None:
            raise NeatValueError("Failed to create CogniteConcepts")
        return unverified.unverified_data_model.as_verified_data_model()

    @staticmethod
    def _find_cognite_property(
        property_: str,
        parents: set[ConceptEntity],
        cognite_properties: dict[tuple[ConceptEntity, str], PhysicalProperty],
    ) -> PhysicalProperty | None:
        """Find the parent class that has the property in the cognite properties"""
        for parent in parents:
            if (parent, property_) in cognite_properties:
                return cognite_properties[(parent, property_)]
        return None


class _PhysicalDataModelConverter:
    def __init__(self, data_model: PhysicalDataModel, instance_namespace: Namespace | None = None) -> None:
        self.physical_data_model = data_model
        self.instance_namespace = instance_namespace

    def as_conceptual_data_model(
        self,
    ) -> "ConceptualDataModel":
        from cognite.neat.v0.core._data_model.models.conceptual._verified import (
            Concept,
            ConceptualDataModel,
            ConceptualProperty,
        )

        metadata = self._convert_physical_to_conceptual_metadata(self.physical_data_model.metadata)

        concepts: list[Concept] = []
        for view in self.physical_data_model.views:
            concept = Concept(
                # we do not want a version in class as we use URI for the class
                concept=ConceptEntity(prefix=view.view.prefix, suffix=view.view.suffix),
                description=view.description,
                name=view.name,
                implements=[
                    # we do not want a version in class as we use URI for the class
                    implemented_view.as_concept_entity(skip_version=True)
                    for implemented_view in view.implements or []
                ],
            )

            # Linking
            concept.physical = view.neatId
            concepts.append(concept)

        prefixes = get_default_prefixes_and_namespaces()
        if self.instance_namespace:
            instance_prefix = next((k for k, v in prefixes.items() if v == self.instance_namespace), None)
            if instance_prefix is None:
                # We need to add a new prefix
                instance_prefix = f"prefix_{len(prefixes) + 1}"
                prefixes[instance_prefix] = self.instance_namespace

        properties: list[ConceptualProperty] = []
        value_type: DataType | ConceptEntity | str
        for property_ in self.physical_data_model.properties:
            if isinstance(property_.value_type, DataType):
                value_type = property_.value_type
            elif isinstance(property_.value_type, ViewEntity):
                value_type = ConceptEntity(
                    prefix=property_.value_type.prefix,
                    suffix=property_.value_type.suffix,
                )
            elif isinstance(property_.value_type, PhysicalUnknownEntity):
                value_type = UnknownEntity()
            else:
                raise ValueError(f"Unsupported value type: {property_.value_type.type_}")

            conceptual_property = ConceptualProperty(
                # Removing version
                concept=ConceptEntity(suffix=property_.view.suffix, prefix=property_.view.prefix),
                property_=property_.view_property,
                name=property_.name,
                value_type=value_type,
                description=property_.description,
                min_count=property_.min_count,
                max_count=property_.max_count,
            )

            # Linking
            conceptual_property.physical = property_.neatId

            properties.append(conceptual_property)

        conceptual_data_model = ConceptualDataModel(
            metadata=metadata,
            properties=SheetList[ConceptualProperty](properties),
            concepts=SheetList[Concept](concepts),
            prefixes=prefixes,
        )

        self.physical_data_model.sync_with_conceptual_data_model(conceptual_data_model)

        return conceptual_data_model

    @classmethod
    def _convert_physical_to_conceptual_metadata(cls, metadata: PhysicalMetadata) -> "ConceptualMetadata":
        from cognite.neat.v0.core._data_model.models.conceptual._verified import (
            ConceptualMetadata,
        )

        return ConceptualMetadata(
            space=metadata.space,
            external_id=metadata.external_id,
            version=metadata.version,
            description=metadata.description,
            name=metadata.name,
            creator=metadata.creator,
            created=metadata.created,
            updated=metadata.updated,
        )


class _SubsetEditableCDMPhysicalDataModel(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel]):
    """Subsets editable CDM data model to only include desired set of CDM concepts.

    !!! note "Platypus UI limitations"
        This is temporal solution to enable cleaner extension of core data model,
        assuring that Platypus UI will work correctly, including Data Model Editor,
        Query Explorer and Search.
    """

    def __init__(self, views: set[ViewEntity]):
        if not_in_cognite_core := {view.external_id for view in views} - set(COGNITE_CONCEPTS):
            raise NeatValueError(
                f"Concept(s) {', '.join(not_in_cognite_core)} is/are not part of the Cognite Core Data Model. Aborting."
            )

        self._views = views

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        # should check to make sure data model is based on the editable CDM
        # if not raise an error

        subsetted_data_model: dict[str, Any] = {
            "metadata": data_model.metadata.model_copy(),
            "views": SheetList[PhysicalView](),
            "properties": SheetList[PhysicalProperty](),
            "containers": SheetList[PhysicalContainer](),
            "enum": data_model.enum,
            "nodes": data_model.nodes,
        }

        containers_to_keep = set()

        if editable_views_to_keep := self._editable_views_to_keep(data_model):
            for view in data_model.views:
                if view.view in editable_views_to_keep or view.view.space in COGNITE_SPACES:
                    subsetted_data_model["views"].append(view)

            for property_ in data_model.properties:
                if property_.view in editable_views_to_keep and (
                    isinstance(property_.value_type, DataType)
                    or isinstance(property_.value_type, PhysicalUnknownEntity)
                    or (isinstance(property_.value_type, ViewEntity) and property_.value_type in editable_views_to_keep)
                ):
                    subsetted_data_model["properties"].append(property_)
                    if property_.container:
                        containers_to_keep.add(property_.container)

            if data_model.containers:
                for container in data_model.containers:
                    if container.container in containers_to_keep:
                        subsetted_data_model["containers"].append(container)
            try:
                return PhysicalDataModel.model_validate(subsetted_data_model)
            except ValidationError as e:
                raise NeatValueError(f"Cannot subset data_model: {e}") from e
        else:
            raise NeatValueError("Cannot subset data_model: provided data model is not based on Core Data Model")

    def _editable_views_to_keep(self, data_model: PhysicalDataModel) -> set[ViewEntity]:
        return {
            view.view
            for view in data_model.views
            if view.view.space not in COGNITE_SPACES
            and view.implements
            and any(implemented in self._views for implemented in view.implements)
        }


class SubsetPhysicalDataModel(VerifiedDataModelTransformer[PhysicalDataModel, PhysicalDataModel]):
    """Subsets physical data model to only include the specified views."""

    def __init__(self, views: set[ViewEntity]):
        self._views = views

    def transform(self, data_model: PhysicalDataModel) -> PhysicalDataModel:
        analysis = DataModelAnalysis(physical=data_model)

        views_by_view = analysis.view_by_view_entity
        implements_by_view = analysis.implements_by_view()

        available = analysis.defined_views(include_ancestors=True)
        subset = available.intersection(self._views)

        ancestors: set[ViewEntity] = set()
        for view in subset:
            ancestors = ancestors.union({ancestor for ancestor in get_inheritance_path(view, implements_by_view)})
        subset = subset.union(ancestors)

        if not subset:
            raise NeatValueError("None of the requested views are defined in the data_model!")

        if nonexisting := self._views - subset:
            raise NeatValueError(
                "Following requested views do not exist"
                f" in the data_model: [{','.join([view.external_id for view in nonexisting])}]. Aborting."
            )

        subsetted_data_model: dict[str, Any] = {
            "metadata": data_model.metadata.model_copy(),
            "views": SheetList[PhysicalView](),
            "properties": SheetList[PhysicalProperty](),
            "containers": SheetList[PhysicalContainer](),
            "enum": data_model.enum,
            "nodes": data_model.nodes,
        }

        # add views
        for view in subset:
            subsetted_data_model["views"].append(views_by_view[view])

        used_containers = set()

        # add properties
        for view, properties in analysis.properties_by_view(include_ancestors=False).items():
            if view not in subset:
                continue

            for property_ in properties:
                if (
                    isinstance(property_.value_type, DataType)
                    or isinstance(property_.value_type, PhysicalUnknownEntity)
                    or (isinstance(property_.value_type, ViewEntity) and property_.value_type in subset)
                ):
                    subsetted_data_model["properties"].append(property_)

                    if property_.container:
                        used_containers.add(property_.container)

        # add containers
        if data_model.containers:
            for container in data_model.containers:
                if container.container in used_containers:
                    subsetted_data_model["containers"].append(container)

        try:
            return PhysicalDataModel.model_validate(subsetted_data_model)
        except ValidationError as e:
            raise NeatValueError(f"Cannot subset data_model: {e}") from e


class SubsetConceptualDataModel(VerifiedDataModelTransformer[ConceptualDataModel, ConceptualDataModel]):
    """Subsets Conceptual Data Model to only include the specified concepts."""

    def __init__(self, concepts: set[ConceptEntity]):
        self._concepts = concepts

    def transform(self, data_model: ConceptualDataModel) -> ConceptualDataModel:
        analysis = DataModelAnalysis(conceptual=data_model)

        concept_by_concept_entity = analysis.concept_by_concept_entity
        parent_entity_by_concept_entity = analysis.parents_by_concept()

        available = analysis.defined_concepts(include_ancestors=True)
        subset = available.intersection(self._concepts)

        # need to add all the parent classes of the desired classes to the possible classes
        ancestors: set[ConceptEntity] = set()
        for concept in subset:
            ancestors = ancestors.union(
                {ancestor for ancestor in get_inheritance_path(concept, parent_entity_by_concept_entity)}
            )
        subset = subset.union(ancestors)

        if not subset:
            raise NeatValueError("None of the requested concepts are defined in the data_model!")

        if nonexisting := self._concepts - subset:
            raise NeatValueError(
                "Following requested concepts do not exist"
                f" in the data_model: [{','.join([concept.suffix for concept in nonexisting])}]"
                ". Aborting."
            )

        subsetted_data_model: dict[str, Any] = {
            "metadata": data_model.metadata.model_copy(),
            "prefixes": (data_model.prefixes or {}).copy(),
            "concepts": SheetList[Concept](),
            "properties": SheetList[ConceptualProperty](),
        }

        for concept in subset:
            subsetted_data_model["concepts"].append(concept_by_concept_entity[concept])

        for concept, properties in analysis.properties_by_concepts(include_ancestors=False).items():
            if concept not in subset:
                continue
            for property_ in properties:
                # datatype property can be added directly
                if (
                    isinstance(property_.value_type, DataType)
                    or (isinstance(property_.value_type, ConceptEntity) and property_.value_type in subset)
                    or isinstance(property_.value_type, UnknownEntity)
                ):
                    subsetted_data_model["properties"].append(property_)
                # object property can be added if the value type is in the subset
                elif isinstance(property_.value_type, MultiValueTypeInfo):
                    allowed = [t for t in property_.value_type.types if t in subset or isinstance(t, DataType)]
                    if allowed:
                        subsetted_data_model["properties"].append(
                            property_.model_copy(
                                deep=True,
                                update={"value_type": MultiValueTypeInfo(types=allowed)},
                            )
                        )

        try:
            return ConceptualDataModel.model_validate(subsetted_data_model)
        except ValidationError as e:
            raise NeatValueError(f"Cannot subset data_model: {e}") from e


class AddCogniteProperties(
    DataModelTransformer[
        ImportedDataModel[UnverifiedConceptualDataModel],
        ImportedDataModel[UnverifiedConceptualDataModel],
    ]
):
    """This transformer looks at the implements of the classes and adds all properties
    from the parent (and ancestors) classes that are not already included in the data model.

    Args:
        client: The client is used to look up the properties of the parent classes.
        dummy_property: A dummy property is added to the user defined concepts

    """

    def __init__(self, client: NeatClient, dummy_property: str | None = None) -> None:
        self._client = client
        self._dummy_property = dummy_property

    @property
    def description(self) -> str:
        """Get the description of the transformer."""
        return "Add Cognite properties for all concepts that implements a Cognite concept."

    def transform(
        self, data_model: ImportedDataModel[UnverifiedConceptualDataModel]
    ) -> ImportedDataModel[UnverifiedConceptualDataModel]:
        input_ = data_model.unverified_data_model
        if input_ is None:
            raise NeatValueError("Data model read failed. Cannot add cognite properties to None data_model.")

        default_space = input_.metadata.space
        default_version = input_.metadata.version

        dependencies_by_concept = self._get_dependencies_by_concepts(input_.concepts, data_model.context, default_space)

        properties_by_concepts = self._get_properties_by_concepts(input_.properties, data_model.context, default_space)

        cognite_implements_concepts = self._get_cognite_concepts(dependencies_by_concept)
        views_by_concept_entity = self._get_views_by_concept(
            cognite_implements_concepts, default_space, default_version
        )

        for concept_entity, view in views_by_concept_entity.items():
            for prop_id, view_prop in view.properties.items():
                if prop_id in properties_by_concepts[concept_entity]:
                    continue
                properties_by_concepts[concept_entity][prop_id] = DMSImporter.as_unverified_conceptual_property(
                    concept_entity, prop_id, view_prop
                )

        try:
            topological_order = TopologicalSorter(dependencies_by_concept).static_order()
        except CycleError as e:
            raise NeatValueError(f"Cycle detected in the class hierarchy: {e}") from e

        new_properties: list[UnverifiedConceptualProperty] = input_.properties.copy()
        for concept_entity in topological_order:
            if concept_entity not in dependencies_by_concept:
                continue
            for parent in dependencies_by_concept[concept_entity]:
                for prop in properties_by_concepts[parent].values():
                    if prop.property_ not in properties_by_concepts[concept_entity]:
                        new_prop = prop.copy(
                            update={"Concept": concept_entity},
                            default_prefix=default_space,
                        )
                        new_properties.append(new_prop)
                        properties_by_concepts[concept_entity][prop.property_] = new_prop

            if self._dummy_property:
                new_properties.append(
                    UnverifiedConceptualProperty(
                        concept=concept_entity,
                        property_=f"{to_camel_case(concept_entity.suffix)}{self._dummy_property}",
                        value_type=String(),
                        min_count=0,
                        max_count=1,
                    )
                )

        new_classes: list[UnverifiedConcept] = input_.concepts.copy()
        existing_classes = {cls.concept for cls in input_.concepts}
        for concept_entity, view in views_by_concept_entity.items():
            if concept_entity not in existing_classes:
                new_classes.append(DMSImporter.as_unverified_concept(view))
                existing_classes.add(concept_entity)

        return ImportedDataModel(
            unverified_data_model=UnverifiedConceptualDataModel(
                metadata=input_.metadata,
                properties=new_properties,
                concepts=new_classes,
                prefixes=input_.prefixes,
            ),
            context=None,
        )

    @staticmethod
    def _get_properties_by_concepts(
        properties: list[UnverifiedConceptualProperty],
        read_context: ImportContext | None,
        default_space: str,
    ) -> dict[ConceptEntity, dict[str, UnverifiedConceptualProperty]]:
        issues = IssueList()
        properties_by_class: dict[ConceptEntity, dict[str, UnverifiedConceptualProperty]] = defaultdict(dict)
        for prop in properties:
            try:
                dumped = prop.dump(default_prefix=default_space)
            except ValidationError as e:
                issues.extend(from_pydantic_errors(e.errors(), read_context))
                continue
            concept_entity = cast(ConceptEntity, dumped["Concept"])
            properties_by_class[concept_entity][prop.property_] = prop
        if issues.has_errors:
            raise issues.as_errors(operation="Reading properties")
        return properties_by_class

    @staticmethod
    def _get_dependencies_by_concepts(
        concepts: list[UnverifiedConcept],
        read_context: ImportContext | None,
        default_space: str,
    ) -> dict[ConceptEntity, set[ConceptEntity]]:
        dependencies_by_concepts: dict[ConceptEntity, set[ConceptEntity]] = {}
        issues = IssueList()
        for raw in concepts:
            try:
                dumped = raw.dump(default_prefix=default_space)
            except ValidationError as e:
                issues.extend(from_pydantic_errors(e.errors(), read_context))
                continue
            concept_entity = cast(ConceptEntity, dumped["Concept"])
            implements = cast(list[ConceptEntity] | None, dumped["Implements"])
            dependencies_by_concepts[concept_entity] = set(implements or [])
        if issues.has_errors:
            raise issues.as_errors(operation="Reading classes")
        return dependencies_by_concepts

    @staticmethod
    def _get_cognite_concepts(
        dependencies_by_class: dict[ConceptEntity, set[ConceptEntity]],
    ) -> set[ConceptEntity]:
        cognite_implements_concepts = {
            dependency
            for dependencies in dependencies_by_class.values()
            for dependency in dependencies
            if dependency.prefix in COGNITE_SPACES
        }
        if not cognite_implements_concepts:
            raise NeatValueError("None of the classes implement Cognite Core concepts.")
        return cognite_implements_concepts

    def _get_views_by_concept(
        self, concepts: set[ConceptEntity], default_space: str, default_version: str
    ) -> dict[ConceptEntity, View]:
        view_ids = [concept.as_view_entity(default_space, default_version).as_id() for concept in concepts]
        views = self._client.loaders.views.retrieve(view_ids, include_ancestor=True, include_connected=True)
        return {ConceptEntity(prefix=view.space, suffix=view.external_id, version=view.version): view for view in views}
