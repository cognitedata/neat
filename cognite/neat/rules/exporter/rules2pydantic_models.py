import re
import sys
import warnings
from collections.abc import Iterable
from datetime import datetime
from typing import Any, TypeAlias, cast


from cognite.client.data_classes import Asset, Relationship
from cognite.client.data_classes.data_modeling import EdgeApply, MappedPropertyApply, NodeApply, NodeOrEdgeData
from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic._internal._model_construction import ModelMetaclass
from rdflib import Graph, URIRef
from typing_extensions import TypeAliasType

from cognite.neat.graph.loaders.core.rdf_to_assets import NeatMetadataKeys
from cognite.neat.graph.transformations.query_generator.sparql import build_construct_query, triples2dictionary
from cognite.neat.rules import exceptions
from cognite.neat.rules.analysis import (
    define_class_asset_mapping,
    define_class_relationship_mapping,
    to_class_property_pairs,
)
from cognite.neat.rules.exporter.rules2dms import DataModel
from cognite.neat.rules.models import Property, TransformationRules, type_to_target_convention

if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    from datetime import timezone

    UTC = timezone.utc


EdgeOneToOne: TypeAlias = TypeAliasType("EdgeOneToOne", str)  # type: ignore[valid-type]
EdgeOneToMany: TypeAlias = TypeAliasType("EdgeOneToMany", list[str])  # type: ignore[valid-type]


def default_model_configuration():
    return ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, arbitrary_types_allowed=True, strict=False, extra="allow"
    )


def default_model_methods():
    return [from_graph, to_asset, to_relationship, to_node, to_edge, to_graph]


def default_model_property_attributes():
    return [attributes, edges_one_to_one, edges_one_to_many]


def rules_to_pydantic_models(
    transformation_rules: TransformationRules, methods: list | None = None, property_attributes: list | None = None
) -> dict[str, ModelMetaclass]:
    """
    Generate pydantic models from transformation rules.

    Args:
        transformation_rules: Transformation rules
        methods: List of methods to register for pydantic models, by default None.
        property_attributes: List of property attributes to register for pydantic models, by default None.

    Returns:
        Dictionary containing pydantic models

    !!! note "Limitations"
        Currently this will take only unique properties and those which column rule_type
        is set to rdfpath, hence only_rdfpath = True. This means that at the moment
        we do not support UNION, i.e. ability to handle multiple rdfpaths for the same
        property. This is needed option and should be added in the second version of the exporter.
    """
    if methods is None:
        methods = default_model_methods()
    if property_attributes is None:
        property_attributes = default_model_property_attributes()

    class_property_pairs = to_class_property_pairs(transformation_rules, only_rdfpath=True)

    models: dict[str, ModelMetaclass] = {}
    for class_, properties in class_property_pairs.items():
        # generate fields from define properties
        fields = _properties_to_pydantic_fields(properties)

        # store default class to relationship mapping field
        # which is used by the `to_relationship` method
        fields["class_to_asset_mapping"] = (
            dict[str, list[str]],
            Field(define_class_asset_mapping(transformation_rules, class_)),
        )

        # store default class to relationship mapping field
        # which is used by the `to_relationship` method
        fields["class_to_relationship_mapping"] = (
            dict[str, list[str]],
            Field(define_class_relationship_mapping(transformation_rules, class_)),
        )

        fields["data_set_id"] = (
            int,
            Field(
                transformation_rules.metadata.data_set_id or None,
            ),
        )

        model = _dictionary_to_pydantic_model(class_, fields, methods=methods, property_attributes=property_attributes)

        models[class_] = model

    return models


def _properties_to_pydantic_fields(
    properties: dict[str, Property],
) -> dict[str, tuple[EdgeOneToMany | EdgeOneToOne | type | list[type], Any]]:
    """Turns definition of properties into pydantic fields.

    Parameters
    ----------
    properties : dict[str, Property]
        Dictionary of properties

    Returns
    -------
    dict[str, tuple[EdgeOneToMany | EdgeOneToOne | type | list[type], Any]]
        Dictionary of pydantic fields
    """

    fields: dict[str, tuple[EdgeOneToMany | EdgeOneToOne | type | list[type], Any]]

    fields = {"external_id": (str, Field(..., alias="external_id"))}

    for name, property_ in properties.items():
        field_type = _define_field_type(property_)

        field_definition: dict = {
            "alias": name,
            # keys below will be available under json_schema_extra
            "property_type": field_type.__name__ if field_type in [EdgeOneToOne, EdgeOneToMany] else "NodeAttribute",
            "property_value_type": property_.expected_value_type,
        }

        if field_type.__name__ in [EdgeOneToMany.__name__, list.__name__]:
            field_definition["min_length"] = property_.min_count
            field_definition["max_length"] = property_.max_count

        if not property_.is_mandatory and not property_.default:
            field_definition["default"] = None
        elif property_.default:
            field_definition["default"] = property_.default

        # making sure that field names are python compliant
        # their original names are stored as aliases
        fields[re.sub(r"[^_a-zA-Z0-9/_]", "_", name)] = (
            field_type,
            Field(**field_definition),  # type: ignore[pydantic-field]
        )

    return fields


def _define_field_type(property_: Property):
    if property_.property_type == "ObjectProperty" and property_.max_count == 1:
        return EdgeOneToOne
    elif property_.property_type == "ObjectProperty":
        return EdgeOneToMany
    elif property_.property_type == "DatatypeProperty" and property_.max_count == 1:
        return type_to_target_convention(property_.expected_value_type, "python")
    else:
        inner_type = type_to_target_convention(property_.expected_value_type, "python")
        return list[inner_type]  # type: ignore[valid-type]


def _dictionary_to_pydantic_model(
    name: str,
    model_definition: dict,
    model_configuration: ConfigDict | None = None,
    methods: list | None = None,
    property_attributes: list | None = None,
    validators: list | None = None,
) -> type[BaseModel]:
    """Generates pydantic model from dictionary containing definition of fields.
    Additionally, it adds methods to the model and validators.

    Parameters
    ----------
    name : str
        Name of the model
    model_definition : dict
        Dictionary containing definition of fields
    model_configuration : ConfigDict, optional
        Configuration of pydantic model, by default None
    methods : list, optional
        Methods that work on fields once model is instantiated, by default None
    property_attributes : list, optional
        Property attributed that work on model fields once model is instantiated, by default None
    validators : list, optional
        Any custom validators to be added in addition to base pydantic ones, by default None

    Returns
    -------
    type[BaseModel]
        Pydantic model
    """

    if model_configuration:
        model_configuration = default_model_configuration()

    fields: dict[str, tuple | type[BaseModel]] = {}

    for field_name, value in model_definition.items():
        if isinstance(value, tuple):
            fields[field_name] = value
        elif isinstance(value, dict):
            fields[field_name] = (_dictionary_to_pydantic_model(f"{name}_{field_name}", value), ...)
        else:
            raise exceptions.FieldValueOfUnknownType(field_name, value)

    model = create_model(name, __config__=model_configuration, **fields)  # type: ignore[call-overload]

    if methods:
        for method in methods:
            setattr(model, method.__name__, method)
    if property_attributes:
        for property_attribute in property_attributes:
            setattr(model, property_attribute.fget.__name__, property_attribute)

    # any additional validators to be added
    if validators:
        ...

    return model


@property  # type: ignore[misc]
def attributes(self) -> list[str]:
    return [
        field
        for field in self.model_fields_set
        if (schema := self.model_fields[field].json_schema_extra) and schema.get("property_type") == "NodeAttribute"
    ]


@property  # type: ignore[misc]
def edges_one_to_one(self) -> list[str]:
    return [
        field
        for field in self.model_fields_set
        if (schema := self.model_fields[field].json_schema_extra) and schema.get("property_type") == "EdgeOneToOne"
    ]


@property  # type: ignore[misc]
def edges_one_to_many(self) -> list[str]:
    return [
        field
        for field in self.model_fields_set
        if (schema := self.model_fields[field].json_schema_extra) and schema.get("property_type") == "EdgeOneToMany"
    ]


# Define methods that work on model instance
@classmethod  # type: ignore[misc]
def from_graph(
    cls,
    graph: Graph,
    transformation_rules: TransformationRules,
    external_id: URIRef,
    incomplete_instance_allowed: bool = True,
):
    """Method that creates model instance from class instance stored in graph.

    Args:
        graph: Graph containing triples of class instance
        transformation_rules: Transformation rules
        external_id: External id of class instance to be used to instantiate associated pydantic model
        incomplete_instance_allowed: Flag allowing incomplete instances to be queried. Defaults to True.

    Raises:
        exceptions.MissingInstanceTriples: _description_
        exceptions.PropertyRequiredButNotProvided: _description_

    Returns:
        Pydantic model instance
    """

    # build sparql query for given object
    class_ = cls.__name__

    # here properties_optional is set to True in order to also return
    # incomplete class instances so we catch them and raise exceptions
    sparql_construct_query = build_construct_query(
        graph,
        class_,
        transformation_rules,
        class_instances=[external_id],
        properties_optional=incomplete_instance_allowed,
    )
    # In the docs, a construct query is said to return triple
    # Not sure if the triple will be URIRef or Literal
    query_result = cast(Iterable[tuple[URIRef, URIRef, str | URIRef]], graph.query(sparql_construct_query))

    result = triples2dictionary(query_result)

    if not result:
        raise exceptions.MissingInstanceTriples(external_id)

    # wrangle results to dict
    args: dict[str, list[str] | str] = {}
    for field in cls.model_fields.values():
        # if field is not required and not in result, skip
        if not field.is_required() and field.alias not in result:
            continue

        # if field is required and not in result, raise error
        if field.is_required() and field.alias not in result:
            raise exceptions.PropertyRequiredButNotProvided(field.alias, external_id)

        # flatten result if field is not edge or list of values
        if field.annotation.__name__ not in [EdgeOneToMany.__name__, list.__name__]:
            if isinstance(result[field.alias], list) and len(result[field.alias]) > 1:
                warnings.warn(
                    exceptions.FieldContainsMoreThanOneValue(
                        field.alias,
                        len(result[field.alias]),
                    ).message,
                    category=exceptions.FieldContainsMoreThanOneValue,
                    stacklevel=2,
                )

            args[field.alias] = result[field.alias][0]
        else:
            args[field.alias] = result[field.alias]

    return cls(**args)


# define methods that creates asset out of model id (default)
def to_asset(
    self,
    add_system_metadata: bool = True,
    metadata_keys: NeatMetadataKeys | None = None,
    add_labels: bool = True,
    data_set_id: int | None = None,
) -> Asset:
    """Convert model instance to asset.

    Parameters
    ----------
    add_system_metadata : bool, optional
        Flag indicating to add or not system/neat metadata, by default True
    metadata_keys : NeatMetadataKeys | None, optional
        Definition of system/neat metadata, by default None
    add_labels : bool, optional
        To add or not labels to asset, by default True
    data_set_id : int, optional
        Data set id to which asset belongs to, by default None

    Returns
    -------
    Asset
        Asset instance
    """
    # Needs copy otherwise modifications impact all instances
    class_instance_dictionary = self.model_dump(by_alias=True)
    adapted_mapping_config = _adapt_mapping_config_by_instance(
        self.external_id, class_instance_dictionary, self.class_to_asset_mapping
    )
    asset = _class_to_asset_instance_dictionary(class_instance_dictionary, adapted_mapping_config)

    # set default metadata keys if not provided
    metadata_keys = NeatMetadataKeys() if metadata_keys is None else metadata_keys

    # add system metadata
    if add_system_metadata:
        _add_system_metadata(self, metadata_keys, asset)

    if add_labels:
        asset["labels"] = [asset["metadata"][metadata_keys.type], "non-historic"]

    if data_set_id:
        return Asset(**asset, data_set_id=data_set_id)
    else:
        return Asset(**asset, data_set_id=self.data_set_id)


def _add_system_metadata(self, metadata_keys: NeatMetadataKeys, asset: dict):
    asset["metadata"][metadata_keys.type] = self.__class__.__name__
    asset["metadata"][metadata_keys.identifier] = self.external_id
    now = str(datetime.now(UTC))
    asset["metadata"][metadata_keys.start_time] = now
    asset["metadata"][metadata_keys.update_time] = now
    asset["metadata"][metadata_keys.active] = "true"


def _adapt_mapping_config_by_instance(external_id, class_instance_dictionary, mapping_config):
    adapted_mapping_config = {}
    for asset_field, class_properties in mapping_config.items():
        if asset_field != "metadata":
            # We are selecting first property that is available in the graph
            # and add it to corresponding asset field and exit loop
            for property_ in class_properties:
                if class_instance_dictionary.get(property_, None):
                    adapted_mapping_config[asset_field] = property_
                    break

        elif metadata_keys := [
            property_ for property_ in class_properties if class_instance_dictionary.get(property_, None)
        ]:
            adapted_mapping_config["metadata"] = metadata_keys

    # Raise warnings for fields that will miss in asset
    for asset_field in mapping_config:
        if asset_field not in adapted_mapping_config:
            warnings.warn(
                exceptions.FieldNotFoundInInstance(external_id, asset_field).message,
                category=exceptions.FieldNotFoundInInstance,
                stacklevel=2,
            )

    return adapted_mapping_config


def _class_to_asset_instance_dictionary(class_instance_dictionary, mapping_config):
    for key, values in mapping_config.items():
        if key != "metadata":
            mapping_config[key] = class_instance_dictionary.get(values, None)
        else:
            mapping_config[key] = {value: class_instance_dictionary.get(value, None) for value in values}

    return mapping_config


def to_relationship(self, transformation_rules: TransformationRules) -> Relationship:
    """Creates relationship instance from model instance."""
    raise NotImplementedError()


def to_node(self, data_model: DataModel, add_class_prefix: bool) -> NodeApply:
    """Creates DMS node from pydantic model."""

    if not set(self.attributes + self.edges_one_to_one + self.edges_one_to_many).issubset(
        set(data_model.containers[self.__class__.__name__].properties.keys())
    ):
        raise exceptions.InstancePropertiesNotMatchingContainerProperties(
            self.__class__.__name__,
            self.attributes + self.edges_one_to_one + self.edges_one_to_many,
            list(data_model.containers[self.__class__.__name__].properties.keys()),
        )

    attributes: dict = {attribute: self.__getattribute__(attribute) for attribute in self.attributes}
    if add_class_prefix:
        edges_one_to_one: dict = {}
        dm_view = data_model.views[self.__class__.__name__]
        if dm_view.properties:
            for edge in self.edges_one_to_one:
                mapped_property = dm_view.properties[edge]
                if isinstance(mapped_property, MappedPropertyApply):
                    object_view = mapped_property.source
                if object_view:
                    object_class_name = object_view.external_id
                    edges_one_to_one[edge] = {
                        "space": data_model.space,
                        "externalId": add_class_prefix_to_xid(
                            class_name=object_class_name,
                            external_id=self.__getattribute__(edge),
                        ),
                    }
    else:
        edges_one_to_one = {
            edge_one_to_one: {"space": data_model.space, "externalId": self.__getattribute__(edge_one_to_one)}
            for edge_one_to_one in self.edges_one_to_one
        }

    return NodeApply(
        space=data_model.space,
        external_id=self.external_id,
        sources=[
            NodeOrEdgeData(
                source=data_model.views[self.__class__.__name__].as_id(),
                properties=attributes | edges_one_to_one,
            )
        ],
    )


def to_edge(self, data_model: DataModel) -> list[EdgeApply]:
    """Creates DMS edge from pydantic model."""
    edges: list[EdgeApply] = []

    def is_external_id_valid(external_id: str) -> bool:
        # should match "^[^\x00]{1,255}$" and not be None or none
        if external_id == "None" or external_id == "none":
            return False
        return bool(re.match(r"^[^\x00]{1,255}$", external_id))

    for edge_one_to_many in self.edges_one_to_many:
        edge_type_id = f"{self.__class__.__name__}.{edge_one_to_many}"

        edges.extend(
            EdgeApply(
                space=data_model.space,
                external_id=f"{self.external_id}-{end_node_id}",
                type=(data_model.space, edge_type_id),
                start_node=(data_model.space, self.external_id),
                end_node=(
                    data_model.space,
                    end_node_id,
                ),
            )
            for end_node_id in self.__getattribute__(edge_one_to_many)
            if is_external_id_valid(end_node_id)
        )
    return edges


def to_graph(self, transformation_rules: TransformationRules, graph: Graph):
    """Writes instance as set of triples to triple store (Graphs)."""
    ...


def add_class_prefix_to_xid(class_name: str, external_id: str) -> str:
    """Adds class name as prefix to the external_id"""
    return f"{class_name}_{external_id}"
