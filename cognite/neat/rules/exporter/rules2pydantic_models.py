import re
from typing_extensions import TypeAliasType
from pydantic import BaseModel, ConfigDict, Field, create_model
from pydantic._internal._model_construction import ModelMetaclass
from rdflib import Graph, URIRef

from cognite.client.data_classes import Asset, Relationship
from cognite.neat.rules.analysis import to_class_property_pairs, define_asset_class_mapping
from cognite.neat.utils.query_generator.sparql import build_construct_query, triples2dictionary
from cognite.neat.rules.models import TransformationRules, type_to_target_convention


OneToOne = TypeAliasType("OneToOne", str)
OneToMany = TypeAliasType("OneToMany", list[str])


def default_configuration():
    return ConfigDict(
        populate_by_name=True, str_strip_whitespace=True, arbitrary_types_allowed=True, strict=False, extra="allow"
    )


def default_methods():
    return [from_graph, to_asset, to_relationship, to_dms, to_graph]


def rules_to_pydantic_models(
    transformation_rules: TransformationRules, methods: list = None
) -> dict[str, ModelMetaclass]:
    if methods is None:
        methods = default_methods()

    class_property_pairs = to_class_property_pairs(transformation_rules, only_rdfpath=True)

    models: dict[str, ModelMetaclass] = {}
    for class_, properties in class_property_pairs.items():
        fields = _define_fields(properties)
        model = dictionary_to_pydantic_model(
            class_, fields, methods=[from_graph, to_asset, to_relationship, to_dms, to_graph]
        )

        models[class_] = model

        # adding class to asset mapping to model
        # this are extra fields allowed by configuration
        models[class_]._class_to_asset_mapping = define_asset_class_mapping(transformation_rules, class_)
        models[class_].data_set_id = transformation_rules.metadata.data_set_id

    return models


def _define_fields(properties) -> dict[str, tuple[type, Field]]:
    fields = {"external_id": (str, Field(..., alias="external_id"))}

    for name, property_ in properties.items():
        field_type = _define_field_type(property_)

        field: dict = {"alias": name}

        if field_type.__name__ in [OneToMany.__name__, list.__name__]:
            field["min_length"] = property_.min_count
            field["max_length"] = property_.max_count
        if not property_.mandatory:
            field["default"] = None

        pythonic_name = re.sub(r"[^_a-zA-Z0-9/_]", "_", name)
        fields[pythonic_name] = (field_type, Field(**field))

    return fields


def _define_field_type(property_):
    if property_.property_type == "ObjectProperty" and property_.max_count == 1:
        return OneToOne
    elif property_.property_type == "ObjectProperty":
        return OneToMany
    elif property_.property_type == "DatatypeProperty" and property_.max_count == 1:
        return type_to_target_convention(property_.expected_value_type, "python")
    else:
        return list[type_to_target_convention(property_.expected_value_type, "python")]


def dictionary_to_pydantic_model(
    name: str,
    model_definition: dict,
    model_configuration: ConfigDict = None,
    methods: list = None,
    validators: list = None,
) -> type[BaseModel]:
    if model_configuration:
        model_configuration = default_configuration()

    fields = {}

    for field_name, value in model_definition.items():
        if isinstance(value, tuple):
            fields[field_name] = value
        elif isinstance(value, dict):
            fields[field_name] = (dictionary_to_pydantic_model(f"{name}_{field_name}", value), ...)
        else:
            raise ValueError(f"Field {field_name}:{value} has invalid syntax")

    model = create_model(name, __config__=model_configuration, **fields)

    if methods:
        for method in methods:
            setattr(model, method.__name__, method)

    # should be added to model
    if validators:
        ...

    return model


@classmethod
def from_graph(cls, graph: Graph, transformation_rules: TransformationRules, external_id: URIRef):
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

        if field.is_required() and field.alias not in result:
            ...
        # # if field is required and not in result, raise error

        if field.annotation.__name__ not in [OneToMany.__name__, list.__name__]:
            # take first value since it is not a list nor edge
            # raise warning if there are multiple values !
            result[field.alias] = result[field.alias][0]

    return cls(**result)


# define methods that creates asset out of model id (default)
def to_asset(
    self,
    add_system_metadata: bool = True,
    metadata_keys_aliases: dict[str, str] = None,
    add_labels: bool = True,
    data_set_id: int = None,
) -> Asset:
    # Needs copy otherwise modifications impact all instances
    default_mapping_dictionary = self._class_to_asset_mapping.copy()
    class_instance_dictionary = self.model_dump(by_alias=True)

    instance_mapping_dictionary = convert_default_to_instance_mapping_config(
        class_instance_dictionary, default_mapping_dictionary
    )

    asset_dictionary = class_to_asset_instance_dictionary(class_instance_dictionary, instance_mapping_dictionary)

    # Update of metadata
    if metadata_keys_aliases:
        ...

    if add_system_metadata:
        ...

    if metadata_keys_aliases:
        ...

    if add_labels:
        ...

    if data_set_id:
        return Asset(**asset_dictionary, data_set_id=data_set_id)
    else:
        return Asset(**asset_dictionary, data_set_id=self.data_set_id)


def convert_default_to_instance_mapping_config(class_instance_dictionary, mapping_dictionary):
    for key, values in mapping_dictionary.items():
        if key != "metadata":
            for value in values:
                if class_instance_dictionary.get(value, None):
                    # take first value, as it is priority over the rest
                    mapping_dictionary[key] = value
                else:
                    # remove key from dict
                    # raise warning that instance is missing expected properties
                    mapping_dictionary.pop(key)
        else:
            for value in values:
                if not class_instance_dictionary.get(value, None):
                    mapping_dictionary.pop(key)

    return mapping_dictionary


def class_to_asset_instance_dictionary(class_instance_dictionary, mapping_dictionary):
    for key, values in mapping_dictionary.items():
        if key != "metadata":
            mapping_dictionary[key] = class_instance_dictionary.get(values, None)
        else:
            mapping_dictionary[key] = {value: class_instance_dictionary.get(value, None) for value in values}

    return mapping_dictionary


def to_relationship(self, transformation_rules: TransformationRules) -> Relationship:
    ...


def to_dms(self, transformation_rules: TransformationRules):
    ...


def to_graph(self, transformation_rules: TransformationRules, graph: Graph):
    ...
