from datetime import datetime, timezone
import re
from typing import Any
from typing_extensions import TypeAliasType
import warnings
from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic._internal._model_construction import ModelMetaclass
from rdflib import Graph, URIRef

from cognite.client.data_classes import Asset, Relationship
from cognite.neat.graph.loaders.core.rdf_to_assets import NeatMetadataKeys
from cognite.neat.rules.analysis import (
    to_class_property_pairs,
    define_class_asset_mapping,
    define_class_relationship_mapping,
)
from cognite.neat.graph.transformations.query_generator.sparql import build_construct_query, triples2dictionary
from cognite.neat.rules.models import Property, TransformationRules, type_to_target_convention
from cognite.neat.rules import _exceptions

EdgeOneToOne = TypeAliasType("EdgeOneToOne", str)
EdgeOneToMany = TypeAliasType("EdgeOneToMany", list[str])


def default_model_configuration():
    return ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, arbitrary_types_allowed=True, strict=False, extra="allow"
    )


def default_model_methods():
    return [from_graph, to_asset, to_relationship, to_dms, to_graph]


def rules_to_pydantic_models(
    transformation_rules: TransformationRules, methods: list = None
) -> dict[str, ModelMetaclass]:
    """Generate pydantic models from transformation rules.

    Parameters
    ----------
    transformation_rules : TransformationRules
        Transformation rules
    methods : list, optional
        List of methods to register for pydantic models , by default None

    Returns
    -------
    dict[str, ModelMetaclass]
        Dictionary containing pydantic models

    Notes
    -----
    Currently this will take only unique properties and those which column rule_type
    is set to rdfpath, hence only_rdfpath = True. This means that at the moment
    we do not support UNION, i.e. ability to handle multiple rdfpaths for the same
    property. This is needed option and should be added in the second version of the exporter.
    """
    if methods is None:
        methods = default_model_methods()

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

        model = _dictionary_to_pydantic_model(
            class_, fields, methods=[from_graph, to_asset, to_relationship, to_dms, to_graph]
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

    fields: dict[str, tuple[EdgeOneToMany | EdgeOneToOne | type | list[type], Any]] = {}

    fields = {"external_id": (str, Field(..., alias="external_id"))}

    for name, property_ in properties.items():
        field_type = _define_field_type(property_)

        field_definition: dict = {"alias": name}

        if field_type.__name__ in [EdgeOneToMany.__name__, list.__name__]:
            field_definition["min_length"] = property_.min_count
            field_definition["max_length"] = property_.max_count

        if not property_.mandatory and not property_.default:
            field_definition["default"] = None
        elif property_.default:
            field_definition["default"] = property_.default

        # making sure that field names are python compliant
        # their original names are stored as aliases
        fields[re.sub(r"[^_a-zA-Z0-9/_]", "_", name)] = (field_type, Field(**field_definition))

    return fields


def _define_field_type(property_: Property):
    if property_.property_type == "ObjectProperty" and property_.max_count == 1:
        return EdgeOneToOne
    elif property_.property_type == "ObjectProperty":
        return EdgeOneToMany
    elif property_.property_type == "DatatypeProperty" and property_.max_count == 1:
        return type_to_target_convention(property_.expected_value_type, "python")
    else:
        return list[type_to_target_convention(property_.expected_value_type, "python")]


def _dictionary_to_pydantic_model(
    name: str,
    model_definition: dict,
    model_configuration: ConfigDict = None,
    methods: list = None,
    validators: list = None,
) -> type[BaseModel]:
    """Generates pydantic model from dictionary containing definition of fields.
    Additionally it adds methods to the model and validators.

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
    validators : list, optional
        Any custom validators to be added in addition to base pydantic ones, by default None

    Returns
    -------
    type[BaseModel]
        Pydantic model
    """

    if model_configuration:
        model_configuration = default_model_configuration()

    fields = {}

    for field_name, value in model_definition.items():
        if isinstance(value, tuple):
            fields[field_name] = value
        elif isinstance(value, dict):
            fields[field_name] = (_dictionary_to_pydantic_model(f"{name}_{field_name}", value), ...)
        else:
            raise _exceptions.Error40(field_name, value)

    model = create_model(name, __config__=model_configuration, **fields)

    if methods:
        for method in methods:
            setattr(model, method.__name__, method)

    # any additional validators to be added
    if validators:
        ...

    return model


# Define methods that work on model instance
@classmethod
def from_graph(cls, graph: Graph, transformation_rules: TransformationRules, external_id: URIRef):
    """Method that creates model instance from class instance stored in graph.

    Parameters
    ----------
    graph : Graph
        Graph containing triples of class instance
    transformation_rules : TransformationRules
        Transformation rules
    external_id : URIRef
        External id of class instance to be used to instantiate associated pydantic model

    Returns
    -------
    cls
        Pydantic model instance
    """
    # build sparql query for given object
    class_ = cls.__name__
    sparql_query = build_construct_query(
        graph, class_, transformation_rules, class_instances=[external_id], properties_optional=False
    )

    result = triples2dictionary(list(graph.query(sparql_query)))

    # wrangle results to dict
    for field in cls.model_fields.values():
        # if field is not required and not in result, skip
        if not field.is_required() and field.alias not in result:
            continue

        # if field is required and not in result, raise error
        if field.is_required() and field.alias not in result:
            raise _exceptions.Error41(field.alias, external_id)

        # flatten result if field is not edge or list of values
        if field.annotation.__name__ not in [EdgeOneToMany.__name__, list.__name__]:
            if isinstance(result[field.alias], list) and len(result[field.alias]) > 1:
                warnings.warn(
                    _exceptions.Warning41(
                        field.alias,
                        len(result[field.alias]),
                    ).message,
                    category=_exceptions.Warning41,
                    stacklevel=2,
                )

            result[field.alias] = result[field.alias][0]

    return cls(**result)


# define methods that creates asset out of model id (default)
def to_asset(
    self,
    add_system_metadata: bool = True,
    metadata_keys: NeatMetadataKeys | None = None,
    add_labels: bool = True,
    data_set_id: int = None,
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
    default_mapping_config = self.class_to_asset_mapping.copy()
    class_instance_dictionary = self.model_dump(by_alias=True)
    adapted_mapping_config = _adapt_mapping_config_by_instance(
        self.external_id, class_instance_dictionary, default_mapping_config
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
    now = str(datetime.now(timezone.utc))
    asset["metadata"][metadata_keys.start_time] = now
    asset["metadata"][metadata_keys.update_time] = now
    asset["metadata"][metadata_keys.active] = "true"


def _adapt_mapping_config_by_instance(external_id, class_instance_dictionary, mapping_config):
    for key, values in mapping_config.items():
        if key != "metadata":
            for value in values:
                if class_instance_dictionary.get(value, None):
                    # take first value, as it is priority over the rest
                    mapping_config[key] = value
                else:
                    warnings.warn(
                        _exceptions.Warning40(external_id, key).message,
                        category=_exceptions.Warning40,
                        stacklevel=2,
                    )

                    mapping_config.pop(key)
        else:
            for value in values:
                if not class_instance_dictionary.get(value, None):
                    mapping_config.pop(key)

    return mapping_config


def _class_to_asset_instance_dictionary(class_instance_dictionary, mapping_config):
    for key, values in mapping_config.items():
        if key != "metadata":
            mapping_config[key] = class_instance_dictionary.get(values, None)
        else:
            mapping_config[key] = {value: class_instance_dictionary.get(value, None) for value in values}

    return mapping_config


def to_relationship(self, transformation_rules: TransformationRules) -> Relationship:
    """Creates relationship instance from model instance."""
    ...


def to_dms(self, transformation_rules: TransformationRules):
    """Creates instance of dm in CDF."""
    ...


def to_graph(self, transformation_rules: TransformationRules, graph: Graph):
    """Writes instance as set of triples to triple store (Graphs)."""
    ...
