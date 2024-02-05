import re
import sys
import warnings
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any, TypeAlias, cast

from cognite.client.data_classes import Asset, Relationship
from cognite.client.data_classes.data_modeling import EdgeApply, MappedPropertyApply, NodeApply, NodeOrEdgeData, ViewId
from cognite.client.data_classes.data_modeling.views import SingleHopConnectionDefinitionApply, ViewApply
from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic._internal._model_construction import ModelMetaclass
from rdflib import Graph, URIRef
from typing_extensions import TypeAliasType

from cognite.neat.graph.loaders.core.rdf_to_assets import NeatMetadataKeys
from cognite.neat.graph.transformations.query_generator.sparql import build_construct_query, triples2dictionary
from cognite.neat.rules import exceptions
from cognite.neat.rules.analysis import define_class_asset_mapping, to_class_property_pairs
from cognite.neat.rules.exporter._rules2dms import DMSSchemaComponents
from cognite.neat.rules.exporter._validation import are_entity_names_dms_compliant
from cognite.neat.rules.models.rules import Property, Rules
from cognite.neat.rules.models.value_types import ValueTypeMapping
from cognite.neat.utils.utils import generate_exception_report

if sys.version_info >= (3, 11):
    from datetime import UTC
else:
    from datetime import timezone

    UTC = timezone.utc

EdgeOneToOne: TypeAlias = TypeAliasType("EdgeOneToOne", str)  # type: ignore[valid-type]
EdgeOneToMany: TypeAlias = TypeAliasType("EdgeOneToMany", list[str])  # type: ignore[valid-type]


def default_model_configuration(
    external_id: str | None = None,
    name: str | None = None,
    description: str | None = None,
    space: str | None = None,
    version: str | None = None,
) -> ConfigDict:
    return ConfigDict(
        populate_by_name=True,
        str_strip_whitespace=True,
        arbitrary_types_allowed=True,
        strict=False,
        extra="allow",
        json_schema_extra={
            "title": name,
            "description": description,
            "external_id": external_id,
            "name": name,
            "space": space,
            "version": version,
        },
    )


def default_class_methods():
    return [
        from_dict,
        from_graph,
        to_asset,
        to_relationship,
        to_node,
        to_edge,
        get_field_description,
        get_field_name,
    ]


def default_class_property_methods():
    return [model_name, model_external_id, model_description, attributes, edges_one_to_one, edges_one_to_many]


def rules_to_pydantic_models(
    rules: Rules,
    methods: list | None = None,
    add_extra_fields: bool = False,
) -> dict[str, ModelMetaclass]:
    """
    Generate pydantic models from rules.

    Args:
        rules: Rules to generate pydantic models from
        methods: List of methods to register for pydantic models,
                 by default None meaning defaulting to base neat methods.
        add_extra_fields: Flag indicating to add extra fields to pydantic models, by default False

    Returns:
        Dictionary containing pydantic models with class ids as key and pydantic model as value
        containing properties defined for the given class(es) in the rules.


    !!! note "Default NEAT methods"
        Default NEAT methods which are added to the generated pydantic models are:

        - `get_field_description`: Returns description of the field if one exists.
        - `get_field_name`: Returns name of the field if one exists.
        - `model_name`: Returns the name of the model if one exists.
        - `model_external_id`: Returns the external id of the model if one exists.
        - `model_description`: Returns the description of the model if one exists.
        - `from_graph`: Creates model instance from class instance stored in RDF graph.
        - `to_asset`: Creates CDF Asset instance from model instance.
        - `to_node`: Creates DMS node from model instance.
        - `to_edge`: Creates DMS edge from model instance.
        - `attributes`: Returns list of node attributes.
        - `edges_one_to_one`: Returns list of node edges one to one.
        - `edges_one_to_many`: Returns list of node edges one to many.


    !!! note "Limitations"
        Currently this will take only unique properties and those which column rule_type
        is set to rdfpath, hence only_rdfpath = True. This means that at the moment
        we do not support UNION, i.e. ability to handle multiple rdfpaths for the same
        property. This is needed option and should be added in the second version of the exporter.

    !!! note "Classes and Properties must be DMS Compliant"
        Rules must be DMS compliant, i.e. class and property ids must obey the following regex:
        r`(^[a-zA-Z][a-zA-Z0-9_]{0,253}[a-zA-Z0-9]?$)` and must not contain reserved keywords.

        Classes reserved keywords: `Query`, `Mutation`, `Subscription`, `String`, `Int32`,
        `Int64`, `Int`, `Float32`, `Float64`, `Float`,`Timestamp`, `JSONObject`, `Date`,
        `Numeric`, `Boolean`, `PageInfo`, `File`, `Sequence`, `TimeSeries`

        Properties reserved keywords: `space`, `externalId`, `createdTime`, `lastUpdatedTime`,
        `deletedTime`, `edge_id` `node_id`, `project_id`, `property_group`, `seq`, `tg_table_name`, `extensions`
    """

    names_compliant, name_warnings = are_entity_names_dms_compliant(rules, return_report=True)
    if not names_compliant:
        raise exceptions.EntitiesContainNonDMSCompliantCharacters(report=generate_exception_report(name_warnings))

    if methods is None:
        methods = default_class_methods() + default_class_property_methods()

    class_property_pairs = to_class_property_pairs(rules, only_rdfpath=True)

    models: dict[str, ModelMetaclass] = {}
    for class_, properties in class_property_pairs.items():
        # generate fields from define properties
        fields = _properties_to_pydantic_fields(properties)

        if add_extra_fields:
            # store default class to relationship mapping field
            # which is used by the `to_relationship` method
            fields["class_to_asset_mapping"] = (
                dict[str, list[str]],
                Field(
                    define_class_asset_mapping(rules, class_),
                    description="This is a helper field used for generating CDF Asset out of model instance",
                ),
            )

        model = _dictionary_to_pydantic_model(
            model_id=class_,
            model_fields_definition=fields,
            model_name=rules.classes[class_].class_name,
            model_description=rules.classes[class_].description,
            model_methods=methods,
            space=rules.metadata.prefix,
            version=rules.metadata.version,
        )

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

    for property_id, property_ in properties.items():
        field_type = _define_field_type(property_)
        field_definition: dict = {
            "alias": property_.property_name,
            "description": property_.description if property_.description else None,
            # keys below will be available under json_schema_extra
            "property_type": field_type.__name__ if field_type in [EdgeOneToOne, EdgeOneToMany] else "NodeAttribute",
            "property_value_type": property_.expected_value_type.suffix,
            "property_name": property_.property_name,
            "property_id": property_.property_id,
        }

        if field_type.__name__ in [EdgeOneToMany.__name__, list.__name__]:
            field_definition["min_length"] = property_.min_count
            field_definition["max_length"] = property_.max_count

        if not property_.is_mandatory and not property_.default:
            field_definition["default"] = None
        elif property_.default:
            field_definition["default"] = property_.default

        fields[property_id] = (
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
        return cast(ValueTypeMapping, property_.expected_value_type.mapping).python
    else:
        inner_type = cast(ValueTypeMapping, property_.expected_value_type.mapping).python
        return list[inner_type]  # type: ignore[valid-type]


def _dictionary_to_pydantic_model(
    model_id: str,
    model_fields_definition: dict,
    space: str | None = None,
    version: str | None = None,
    model_name: str | None = None,
    model_description: str | None = None,
    model_configuration: ConfigDict | None = None,
    model_methods: list | None = None,
    validators: list | None = None,
) -> type[BaseModel]:
    """Generates pydantic model from dictionary containing definition of fields.
    Additionally, it adds methods to the model and validators.

    Parameters
    ----------
    model_name : str
        Name of the model, typically an id of the class
    model_fields_definition : dict
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

    if not model_configuration:
        model_configuration = default_model_configuration(
            external_id=model_id, space=space, version=version, name=model_name, description=model_description
        )

    fields: dict[str, tuple | type[BaseModel]] = {}

    for field_name, value in model_fields_definition.items():
        if isinstance(value, tuple):
            fields[field_name] = value
        # Nested classes
        elif isinstance(value, dict):
            fields[field_name] = (_dictionary_to_pydantic_model(f"{model_id}_{field_name}", value), ...)
        else:
            raise exceptions.FieldValueOfUnknownType(field_name, value)

    model = create_model(model_id, __config__=model_configuration, **fields)  # type: ignore[call-overload]

    if model_methods:
        for method in model_methods:
            try:
                setattr(model, method.__name__, method)
            except AttributeError:
                try:
                    setattr(model, method.fget.__name__, method)
                except AttributeError:
                    setattr(model, method.__func__.fget.__name__, method)

    # any additional validators to be added
    if validators:
        ...

    return model


@classmethod  # type: ignore
@property
def attributes(cls) -> list[str]:
    return [
        field
        for field in cls.model_fields
        if (schema := cls.model_fields[field].json_schema_extra) and schema.get("property_type") == "NodeAttribute"
    ]


@classmethod  # type: ignore
@property
def edges_one_to_one(cls) -> list[str]:
    return [
        field
        for field in cls.model_fields
        if (schema := cls.model_fields[field].json_schema_extra) and schema.get("property_type") == "EdgeOneToOne"
    ]


@classmethod  # type: ignore
@property
def edges_one_to_many(cls) -> list[str]:
    return [
        field
        for field in cls.model_fields
        if (schema := cls.model_fields[field].json_schema_extra) and schema.get("property_type") == "EdgeOneToMany"
    ]


# Define methods that work on model instance
@classmethod  # type: ignore[misc]
def from_dict(cls, dictionary: dict[str, list[str] | str]):
    # wrangle results to dict
    args: dict[str, list[Any] | Any] = {}
    for field in cls.model_fields.values():
        # if field is not required and not in result, skip
        if not field.is_required() and field.alias not in dictionary:
            continue

        # if field is required and not in result, raise error
        if field.is_required() and field.alias not in dictionary:
            raise exceptions.PropertyRequiredButNotProvided(field.alias, cast(str, dictionary["external_id"]))

        # flatten result if field is not edge or list of values
        if field.annotation.__name__ not in [EdgeOneToMany.__name__, list.__name__]:
            if isinstance(dictionary[field.alias], list) and len(dictionary[field.alias]) > 1:
                warnings.warn(
                    exceptions.FieldContainsMoreThanOneValue(
                        field.alias,
                        len(dictionary[field.alias]),
                    ).message,
                    category=exceptions.FieldContainsMoreThanOneValue,
                    stacklevel=2,
                )

            args[field.alias] = dictionary[field.alias][0]
        else:
            args[field.alias] = dictionary[field.alias]

    return cls(**args)


# Define methods that work on model instance
@classmethod  # type: ignore[misc]
def from_graph(
    cls,
    graph: Graph,
    transformation_rules: Rules,
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

    dictionary = triples2dictionary(query_result)[external_id]

    if not dictionary:
        raise exceptions.MissingInstanceTriples(external_id)

    return cls.from_dict(dictionary)


# define methods that creates asset out of model id (default)
def to_asset(
    self,
    data_set_id: int,
    add_system_metadata: bool = True,
    metadata_keys: NeatMetadataKeys | None = None,
    add_labels: bool = True,
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
    if not self.class_to_asset_mapping:
        raise exceptions.ClassToAssetMappingNotDefined(self.__class__.__name__)

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

    return Asset(**asset, data_set_id=data_set_id)


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


def to_relationship(self, transformation_rules: Rules) -> Relationship:
    """Creates relationship instance from model instance."""
    raise NotImplementedError()


def to_node(
    self, data_model_or_view_id: DMSSchemaComponents | ViewId | None = None, add_class_prefix: bool = False
) -> NodeApply:
    """Creates DMS node from the instance of pydantic model.

    Args:
        data_model_or_view_id: Instance of DataModel or ViewID. Defaults to None.
        add_class_prefix: Whether to add class id (i.e.model name) prefix to external_id of View. Defaults to False.

    Returns:
        Instance of NodeApply containing node information.


    !!! note "Default Behavior"
        If no DataModel or ViewID is passed, then the default behavior is to create node
        using View information which is by default stored under `model_json_schema` attribute of pydantic model.
    !!! note "Limitations"
        Currently adding class prefix is only possible if the node is created if ViewID is passed or
        if pydantic model already contains View information (which default behavior).
    """

    if isinstance(data_model_or_view_id, DMSSchemaComponents):
        return _to_node_using_data_model(self, data_model_or_view_id, add_class_prefix)
    elif isinstance(data_model_or_view_id, ViewId):
        if not data_model_or_view_id.space:
            raise exceptions.SpaceNotDefined()
        if not data_model_or_view_id.external_id:
            raise exceptions.ViewExternalIdNotDefined()
        if not data_model_or_view_id.version:
            raise exceptions.ViewVersionNotDefined()
        return _to_node_using_view_id(self, data_model_or_view_id)
    else:
        space = self.model_json_schema().get("space", None)
        external_id = self.model_json_schema().get("external_id", None)
        version = self.model_json_schema().get("version", None)

        if not space:
            raise exceptions.SpaceNotDefined()
        if not external_id:
            raise exceptions.ViewExternalIdNotDefined()
        if not version:
            raise exceptions.ViewVersionNotDefined()

        return _to_node_using_view_id(self, ViewId(space, external_id, version))


def _to_node_using_view_id(self, view_id: ViewId) -> NodeApply:
    attributes: dict = {
        attribute: getattr(self, attribute).isoformat()
        if isinstance(getattr(self, attribute), date)
        else getattr(self, attribute)
        for attribute in self.attributes
    }

    edges_one_to_one: dict = {}

    for edge in self.edges_one_to_one:
        if external_id := getattr(self, edge):
            edges_one_to_one[edge] = {
                "space": self.model_json_schema()["space"],
                "externalId": external_id,
            }

    return NodeApply(
        space=self.model_json_schema()["space"],
        external_id=self.external_id,
        sources=[
            NodeOrEdgeData(
                source=view_id,
                properties=attributes | edges_one_to_one,
            )
        ],
    )


def _to_node_using_data_model(self, data_model, add_class_prefix) -> NodeApply:
    view_id: str = f"{self.model_json_schema()['space']}:{type(self).__name__}"

    if not set(self.attributes + self.edges_one_to_one).issubset(set(data_model.views[view_id].properties.keys())):
        raise exceptions.InstancePropertiesNotMatchingViewProperties(
            self.__class__.__name__,
            self.attributes + self.edges_one_to_one + self.edges_one_to_many,
            list(data_model.views[view_id].properties.keys()),
        )

    attributes: dict = {
        attribute: getattr(self, attribute).isoformat()
        if isinstance(getattr(self, attribute), date)
        else getattr(self, attribute)
        for attribute in self.attributes
    }
    if add_class_prefix:
        edges_one_to_one: dict = {}
        dm_view = data_model.views[view_id]
        if dm_view.properties:
            for edge in self.edges_one_to_one:
                mapped_property = dm_view.properties[edge]
                if isinstance(mapped_property, MappedPropertyApply):
                    object_view = mapped_property.source
                if object_view:
                    object_class_name = object_view.external_id

                    if external_id := getattr(self, edge):
                        edges_one_to_one[edge] = {
                            "space": data_model.views[view_id].space,
                            "externalId": add_class_prefix_to_xid(
                                class_name=object_class_name,
                                external_id=external_id,
                            ),
                        }
    else:
        edges_one_to_one = {}

        for edge in self.edges_one_to_one:
            if external_id := getattr(self, edge):
                edges_one_to_one[edge] = {
                    "space": self.model_json_schema()["space"],
                    "externalId": external_id,
                }

    return NodeApply(
        space=data_model.views[view_id].space,
        external_id=self.external_id,
        sources=[
            NodeOrEdgeData(
                source=data_model.views[view_id].as_id(),
                properties=attributes | edges_one_to_one,
            )
        ],
    )


def to_edge(self, data_model: DMSSchemaComponents, add_class_prefix: bool = False) -> list[EdgeApply]:
    """Creates DMS edge from pydantic model."""
    edges: list[EdgeApply] = []

    def is_external_id_valid(external_id: str) -> bool:
        # should match "^[^\x00]{1,255}$" and not be None or none
        if external_id == "None" or external_id == "none":
            return False
        return bool(re.match(r"^[^\x00]{1,255}$", external_id))

    class_name: str = type(self).__name__
    view_id: str = f"{self.model_json_schema()['space']}:{class_name}"

    for edge_one_to_many in self.edges_one_to_many:
        edge_type_id = f"{class_name}.{edge_one_to_many}"
        if end_node_ids := getattr(self, edge_one_to_many):
            for end_node_id in end_node_ids:
                if not is_external_id_valid(end_node_id):
                    warnings.warn(
                        message=exceptions.EdgeConditionUnmet(edge_one_to_many).message,
                        category=exceptions.EdgeConditionUnmet,
                        stacklevel=2,
                    )
                end_node_external_id = end_node_id
                if add_class_prefix:
                    end_node_class_name = _get_end_node_class_name(data_model.views[view_id], edge_one_to_many)
                    if end_node_class_name:
                        end_node_external_id = add_class_prefix_to_xid(end_node_class_name, end_node_id)
                    else:
                        warnings.warn(
                            message=exceptions.EdgeConditionUnmet(edge_one_to_many).message,
                            category=exceptions.EdgeConditionUnmet,
                            stacklevel=2,
                        )

                edge = EdgeApply(
                    space=data_model.views[view_id].space,
                    external_id=f"{self.external_id}-{end_node_external_id}",
                    type=(data_model.views[view_id].space, edge_type_id),
                    start_node=(data_model.views[view_id].space, self.external_id),
                    end_node=(data_model.views[view_id].space, end_node_external_id),
                )
                edges.append(edge)
    return edges


def _get_end_node_class_name(view: ViewApply, edge: str) -> str | None:
    """Get the class name of the end node of an edge."""
    if view.properties is None:
        return None
    mapped_instance = view.properties[edge]
    if isinstance(mapped_instance, SingleHopConnectionDefinitionApply) and mapped_instance.source:
        return mapped_instance.source.external_id
    return None


@classmethod  # type: ignore
@property
def model_name(cls) -> str | None:
    """Returns the name of the model if one exists"""
    return cls.model_json_schema().get("class_name", None)


@classmethod  # type: ignore
@property
def model_external_id(cls) -> str | None:
    """Returns the external id of the model if one exists"""
    return cls.model_json_schema().get("class_id", None)


@classmethod  # type: ignore
@property
def model_description(cls) -> str | None:
    """Returns the description of the model if one exists"""
    return cls.model_json_schema().get("description", None)


@classmethod  # type: ignore
def get_field_description(cls, field_id: str) -> str | None:
    """Returns description of the field if one exists"""
    if field_id in cls.model_fields:
        return cls.model_fields[field_id].description
    else:
        return None


@classmethod  # type: ignore
def get_field_name(cls, field_id: str) -> str | None:
    """Returns name of the field if one exists"""
    if field_id in cls.model_fields and cls.model_fields[field_id].json_schema_extra:
        if "property_name" in cls.model_fields[field_id].json_schema_extra:
            return cls.model_fields[field_id].json_schema_extra["property_name"]
    return None


def add_class_prefix_to_xid(class_name: str, external_id: str) -> str:
    """Adds class name as prefix to the external_id"""
    return f"{class_name}_{external_id}"
