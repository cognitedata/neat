import itertools
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar, cast

from cognite.client import data_modeling as dm
from rdflib import RDF, RDFS, Graph, Namespace, URIRef
from rdflib import Literal as RdfLiteral

from cognite.neat._config import GLOBAL_CONFIG
from cognite.neat._constants import NEAT, get_default_prefixes_and_namespaces
from cognite.neat._issues import IssueList
from cognite.neat._issues.warnings import PropertyValueTypeUndefinedWarning
from cognite.neat._rules.analysis import RulesAnalysis
from cognite.neat._rules.models import InformationRules, data_types
from cognite.neat._rules.models.data_types import AnyURI
from cognite.neat._rules.models.entities._single_value import UnknownEntity
from cognite.neat._rules.models.information import (
    InformationClass,
    InformationInputClass,
    InformationInputProperty,
    InformationMetadata,
)
from cognite.neat._store import NeatGraphStore
from cognite.neat._store._provenance import INSTANCES_ENTITY
from cognite.neat._utils.collection_ import iterate_progress_bar
from cognite.neat._utils.rdf_ import remove_namespace_from_uri, uri_to_short_form
from cognite.neat._utils.text import NamingStandardization

from ._base import DEFAULT_NON_EXISTING_NODE_TYPE, BaseRDFImporter

DEFAULT_INFERENCE_DATA_MODEL_ID = ("neat_space", "InferredDataModel", "inferred")

ORDERED_CLASSES_QUERY = """SELECT ?class (count(?s) as ?instances )
                           WHERE { ?s a ?class . }
                           group by ?class order by DESC(?instances)"""

INSTANCES_OF_CLASS_QUERY = """SELECT ?s ?propertyCount WHERE { ?s a <class> . BIND ('Unknown' as ?propertyCount) }"""


INSTANCES_OF_CLASS_RICHNESS_ORDERED_QUERY = """SELECT ?s (COUNT(?p) as ?propertyCount)
                                               WHERE { ?s a <class> ; ?p ?o . }
                                               GROUP BY ?s
                                               ORDER BY DESC(?propertyCount)"""

INSTANCE_PROPERTIES_DEFINITION = """SELECT ?property (count(?property) as ?occurrence) ?dataType ?objectType
                                    WHERE {<instance_id> ?property ?value .

                                           BIND(datatype(?value) AS ?dataType)

                                           OPTIONAL {?value rdf:type ?objectType .}}
                                    GROUP BY ?property ?dataType ?objectType"""


class InferenceImporter(BaseRDFImporter):
    """Infers rules from a triple store.

    Rules inference through analysis of knowledge graph provided in various formats.
    Use the factory methods to create a triple store from sources such as
    RDF files, JSON files, YAML files, XML files, or directly from a graph store.

    ClassVars:
        overwrite_data_types: Mapping of data types to be overwritten. The InferenceImporter will overwrite
            32-bit integer and 32-bit float data types to 64-bit integer and 64-bit float data types

    Args:
        issue_list: Issue list to store issues
        graph: Knowledge graph
        max_number_of_instance: Maximum number of instances to be used in inference
        prefix: Prefix to be used for the inferred model


    """

    overwrite_data_types: ClassVar[Mapping[URIRef, URIRef]] = {
        data_types.Integer.as_xml_uri_ref(): data_types.Long.as_xml_uri_ref(),
        data_types.Float.as_xml_uri_ref(): data_types.Double.as_xml_uri_ref(),
    }

    @classmethod
    def from_graph_store(
        cls,
        store: NeatGraphStore,
        data_model_id: dm.DataModelId | tuple[str, str, str] = DEFAULT_INFERENCE_DATA_MODEL_ID,
        max_number_of_instance: int = -1,
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
        language: str = "en",
    ) -> "InferenceImporter":
        return super().from_graph_store(
            store,
            data_model_id,
            max_number_of_instance,
            non_existing_node_type,
            language,
        )

    @classmethod
    def from_file(
        cls,
        filepath: Path,
        data_model_id: (dm.DataModelId | tuple[str, str, str]) = DEFAULT_INFERENCE_DATA_MODEL_ID,
        max_number_of_instance: int = -1,
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
        language: str = "en",
        source_name: str = "Unknown",
    ) -> "InferenceImporter":
        return super().from_file(
            filepath,
            data_model_id,
            max_number_of_instance,
            non_existing_node_type,
            language,
            source_name=source_name,
        )

    @classmethod
    def from_json_file(
        cls,
        filepath: Path,
        data_model_id: (dm.DataModelId | tuple[str, str, str]) = DEFAULT_INFERENCE_DATA_MODEL_ID,
        max_number_of_instance: int = -1,
        language: str = "en",
    ) -> "InferenceImporter":
        raise NotImplementedError("JSON file format is not supported yet.")

    @classmethod
    def from_yaml_file(
        cls,
        filepath: Path,
        data_model_id: (dm.DataModelId | tuple[str, str, str]) = DEFAULT_INFERENCE_DATA_MODEL_ID,
        max_number_of_instance: int = -1,
        language: str = "en",
    ) -> "InferenceImporter":
        raise NotImplementedError("YAML file format is not supported yet.")

    @classmethod
    def from_xml_file(
        cls,
        filepath: Path,
        data_model_id: (dm.DataModelId | tuple[str, str, str]) = DEFAULT_INFERENCE_DATA_MODEL_ID,
        max_number_of_instance: int = -1,
    ) -> "InferenceImporter":
        raise NotImplementedError("JSON file format is not supported yet.")

    def _to_rules_components(
        self,
    ) -> dict:
        """Convert RDF graph to dictionary defining data model and prefixes of the graph

        Args:
            graph: RDF graph to be converted to TransformationRules object
            max_number_of_instance: Max number of instances to be considered for each class

        Returns:
            Tuple of data model and prefixes of the graph
        """

        classes: dict[str, dict] = {}
        properties: dict[str, dict] = {}
        prefixes: dict[str, Namespace] = {}
        count_by_value_type_by_property: dict[str, dict[str, int]] = defaultdict(Counter)

        # Infers all the classes in the graph
        for class_uri, no_instances in self.graph.query(ORDERED_CLASSES_QUERY):  # type: ignore[misc]
            if (class_id := remove_namespace_from_uri(cast(URIRef, class_uri))) in classes:
                # handles cases when class id is already present in classes
                class_id = f"{class_id}_{len(classes) + 1}"

            classes[class_id] = {
                "class_": class_id,
                "uri": class_uri,
                "comment": f"Inferred from knowledge graph, where this class has <{no_instances}> instances",
            }

            self._add_uri_namespace_to_prefixes(cast(URIRef, class_uri), prefixes)

        instances_query = (
            INSTANCES_OF_CLASS_QUERY if self.max_number_of_instance == -1 else INSTANCES_OF_CLASS_RICHNESS_ORDERED_QUERY
        )

        classes_iterable = iterate_progress_bar(classes.items(), len(classes), "Inferring classes")

        # Infers all the properties of the class
        for class_id, class_definition in classes_iterable:
            for (  # type: ignore[misc]
                instance,
                _,
            ) in self.graph.query(  # type: ignore[misc]
                instances_query.replace("class", class_definition["uri"])
                if self.max_number_of_instance < 0
                else instances_query.replace("class", class_definition["uri"]) + f" LIMIT {self.max_number_of_instance}"
            ):
                for property_uri, occurrence, data_type_uri, object_type_uri in self.graph.query(  # type: ignore[misc]
                    INSTANCE_PROPERTIES_DEFINITION.replace("instance_id", instance)
                ):  # type: ignore[misc]
                    # this is to skip rdf:type property

                    if property_uri == RDF.type:
                        continue
                    property_id = remove_namespace_from_uri(property_uri)
                    self._add_uri_namespace_to_prefixes(cast(URIRef, property_uri), prefixes)

                    if isinstance(data_type_uri, URIRef):
                        data_type_uri = self.overwrite_data_types.get(data_type_uri, data_type_uri)

                    if value_type_uri := (data_type_uri or object_type_uri):
                        self._add_uri_namespace_to_prefixes(cast(URIRef, value_type_uri), prefixes)
                        value_type_id = remove_namespace_from_uri(value_type_uri)

                    # this handles situations when property points to node that is not present in graph
                    else:
                        value_type_id = str(self.non_existing_node_type)

                        issue = PropertyValueTypeUndefinedWarning(
                            resource_type="Property",
                            identifier=f"{class_id}:{property_id}",
                            property_name=property_id,
                            default_action="Remove the property from the rules",
                            recommended_action="Make sure that graph is complete",
                        )

                        if issue not in self.issue_list:
                            self.issue_list.append(issue)

                    id_ = f"{class_id}:{property_id}"

                    definition = {
                        "class_": class_id,
                        "property_": property_id,
                        "max_count": cast(RdfLiteral, occurrence).value,
                        "value_type": value_type_id,
                        "instance_source": (
                            f"{uri_to_short_form(class_definition['uri'], prefixes)}"
                            f"({uri_to_short_form(cast(URIRef, property_uri), prefixes)})"
                        ),
                    }

                    count_by_value_type_by_property[id_][value_type_id] += 1

                    # USE CASE 1: If property is not present in properties
                    if id_ not in properties:
                        definition["value_type"] = {definition["value_type"]}
                        properties[id_] = definition

                    # USE CASE 2: first time redefinition, value type change to multi
                    elif id_ in properties and definition["value_type"] not in properties[id_]["value_type"]:
                        properties[id_]["value_type"].add(definition["value_type"])

                    # always update max_count with the upmost value
                    properties[id_]["max_count"] = max(properties[id_]["max_count"], definition["max_count"])

        # Create multi-value properties otherwise single value
        for property_ in properties.values():
            # Removes non-existing node type from value type prior final conversion to string
            if len(property_["value_type"]) > 1 and str(self.non_existing_node_type) in property_["value_type"]:
                property_["value_type"].remove(str(self.non_existing_node_type))

            if len(property_["value_type"]) > 1:
                property_["value_type"] = ", ".join([str(t) for t in property_["value_type"]])
            else:
                property_["value_type"] = next(iter(property_["value_type"]))

        return {
            "metadata": self._default_metadata().model_dump(),
            "classes": list(classes.values()),
            "properties": list(properties.values()),
            "prefixes": prefixes,
        }

    def _default_metadata(self):
        now = datetime.now(timezone.utc)
        return InformationMetadata(
            space=self.data_model_id.space,
            external_id=self.data_model_id.external_id,
            version=self.data_model_id.version,
            name="Inferred Model",
            creator="NEAT",
            created=now,
            updated=now,
            description="Inferred model from knowledge graph",
        )

    @property
    def source_uri(self) -> URIRef:
        return INSTANCES_ENTITY.id_


# Internal helper class
@dataclass
class _ReadProperties:
    type_uri: URIRef
    property_uri: URIRef
    value_type: URIRef
    parent_uri: URIRef | None
    max_occurrence: int
    instance_count: int


class SubclassInferenceImporter(BaseRDFImporter):
    """Infer subclasses from a triple store.

    Assumes that the graph already is connected to a schema. The classes should
    match the RDF.type of the instances in the graph, while the subclasses should
    match the NEAT.type of the instances in the graph.

    ClassVars:
        overwrite_data_types: Mapping of data types to be overwritten. The InferenceImporter will overwrite
            32-bit integer and 32-bit float data types to 64-bit integer and 64-bit float data types

    Args:
        issue_list: Issue list to store issues
        graph: Knowledge graph
    """

    overwrite_data_types: ClassVar[Mapping[URIRef, URIRef]] = {
        data_types.Integer.as_xml_uri_ref(): data_types.Long.as_xml_uri_ref(),
        data_types.Float.as_xml_uri_ref(): data_types.Double.as_xml_uri_ref(),
    }

    _ordered_class_query = """SELECT DISTINCT ?class (count(?s) as ?instances )
                           WHERE { ?s a ?class }
                           group by ?class order by DESC(?instances)"""

    _type_parent_query = f"""SELECT ?parent ?type
                            WHERE {{ ?s a ?type .
                            ?type <{RDFS.subClassOf}> ?parent }}"""

    _properties_query = """SELECT DISTINCT ?property ?valueType
                         WHERE {{
                            ?s a <{type}> .
                            ?s ?property ?object .
                            OPTIONAL {{ ?object a ?objectType }}
                            BIND(
                               IF(
                                    isLiteral(?object), datatype(?object),
                                    IF(BOUND(?objectType), ?objectType, <{unknown_type}>)
                                ) AS ?valueType
                            )
                        }}"""

    _max_occurrence_query = """SELECT (MAX(?count) AS ?maxCount)
                            WHERE {{
                              {{
                                SELECT ?subject (COUNT(?object) AS ?count)
                                WHERE {{
                                  ?subject a <{type}> .
                                  ?subject <{property}> ?object .
                                }}
                                GROUP BY ?subject
                              }}
                            }}"""

    def __init__(
        self,
        issue_list: IssueList,
        graph: Graph,
        rules: InformationRules | None = None,
        data_model_id: dm.DataModelId | tuple[str, str, str] | None = None,
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
    ) -> None:
        if sum([1 for v in [rules, data_model_id] if v is not None]) != 1:
            raise ValueError("Exactly one of rules or data_model_id must be provided.")
        if data_model_id is not None:
            identifier = data_model_id
        elif rules is not None:
            identifier = rules.metadata.as_data_model_id().as_tuple()  # type: ignore[assignment]
        else:
            raise ValueError("Exactly one of rules or data_model_id must be provided.")
        super().__init__(issue_list, graph, identifier, -1, non_existing_node_type, language="en")
        self._rules = rules

    def _to_rules_components(
        self,
    ) -> dict:
        if self._rules:
            prefixes = self._rules.prefixes.copy()
        else:
            prefixes = get_default_prefixes_and_namespaces()

        parent_by_child = self._read_parent_by_child_from_graph()
        read_properties = self._read_class_properties_from_graph(parent_by_child)
        classes, properties = self._create_classes_properties(read_properties, prefixes)

        if self._rules:
            metadata = self._rules.metadata.model_dump()
            default_space = self._rules.metadata.prefix
        else:
            metadata = self._default_metadata()
            default_space = metadata["space"]
        return {
            "metadata": metadata,
            "classes": [cls.dump(default_space) for cls in classes],
            "properties": [prop.dump(default_space) for prop in properties],
            "prefixes": prefixes,
        }

    def _create_classes_properties(
        self, read_properties: list[_ReadProperties], prefixes: dict[str, Namespace]
    ) -> tuple[list[InformationInputClass], list[InformationInputProperty]]:
        if self._rules:
            existing_classes = {class_.class_.suffix: class_ for class_ in self._rules.classes}
        else:
            existing_classes = {}
        classes: list[InformationInputClass] = []
        properties_by_class_suffix_by_property_id: dict[str, dict[str, InformationInputProperty]] = {}

        # Help for IDE
        type_uri: URIRef
        parent_uri: URIRef
        for parent_uri, parent_class_properties_iterable in itertools.groupby(
            sorted(read_properties, key=lambda x: x.parent_uri or NEAT.EmptyType),
            key=lambda x: x.parent_uri or NEAT.EmptyType,
        ):
            properties_by_class_by_property = self._get_properties_by_class_by_property(
                parent_class_properties_iterable
            )

            parent_suffix: str | None = None
            if parent_uri != NEAT.EmptyType:
                shared_property_uris = set.intersection(
                    *[
                        set(properties_by_property.keys())
                        for properties_by_property in properties_by_class_by_property.values()
                    ]
                )
                parent_suffix = remove_namespace_from_uri(parent_uri)
                self._add_uri_namespace_to_prefixes(parent_uri, prefixes)
                if parent_suffix not in existing_classes:
                    classes.append(InformationInputClass(class_=parent_suffix))
                else:
                    classes.append(InformationInputClass.load(existing_classes[parent_suffix].model_dump()))
            else:
                shared_property_uris = set()
            shared_properties: dict[URIRef, list[_ReadProperties]] = defaultdict(list)
            for type_uri, properties_by_property_uri in properties_by_class_by_property.items():
                class_suffix = remove_namespace_from_uri(type_uri)
                self._add_uri_namespace_to_prefixes(type_uri, prefixes)

                if class_suffix not in existing_classes:
                    classes.append(
                        InformationInputClass(
                            class_=class_suffix,
                            implements=parent_suffix,
                            instance_source=type_uri,
                        )
                    )
                else:
                    classes.append(InformationInputClass.load(existing_classes[class_suffix].model_dump()))

                properties_by_id: dict[str, InformationInputProperty] = {}
                for property_uri, read_properties in properties_by_property_uri.items():
                    if property_uri in shared_property_uris:
                        shared_properties[property_uri].extend(read_properties)
                        continue
                    property_id = remove_namespace_from_uri(property_uri)
                    self._add_uri_namespace_to_prefixes(property_uri, prefixes)
                    property_id_standardized = NamingStandardization.standardize_property_str(property_uri)
                    if existing_prop := properties_by_id.get(property_id_standardized):
                        if not isinstance(existing_prop.instance_source, list):
                            existing_prop.instance_source = (
                                [existing_prop.instance_source] if existing_prop.instance_source else []
                            )
                        existing_prop.instance_source.append(property_uri)
                        continue
                    else:
                        properties_by_id[property_id_standardized] = self._create_property(
                            read_properties, class_suffix, property_uri, property_id, prefixes
                        )
                properties_by_class_suffix_by_property_id[class_suffix] = properties_by_id
            if parent_suffix:
                properties_by_id = {}
                for property_uri, read_properties in shared_properties.items():
                    property_id = remove_namespace_from_uri(property_uri)
                    self._add_uri_namespace_to_prefixes(property_uri, prefixes)
                    property_id_standardized = NamingStandardization.standardize_property_str(property_uri)
                    if existing_prop := properties_by_id.get(property_id_standardized):
                        if not isinstance(existing_prop.instance_source, list):
                            existing_prop.instance_source = (
                                [existing_prop.instance_source] if existing_prop.instance_source else []
                            )
                        existing_prop.instance_source.append(property_uri)
                    else:
                        properties_by_id[property_id_standardized] = self._create_property(
                            read_properties, parent_suffix, property_uri, property_id, prefixes
                        )
        return classes, [
            prop for properties in properties_by_class_suffix_by_property_id.values() for prop in properties.values()
        ]

    @staticmethod
    def _get_properties_by_class_by_property(
        parent_class_properties_iterable: Iterable[_ReadProperties],
    ) -> dict[URIRef, dict[URIRef, list[_ReadProperties]]]:
        properties_by_class_by_property: dict[URIRef, dict[URIRef, list[_ReadProperties]]] = {}
        for class_uri, class_properties_iterable in itertools.groupby(
            sorted(parent_class_properties_iterable, key=lambda x: x.type_uri), key=lambda x: x.type_uri
        ):
            properties_by_class_by_property[class_uri] = defaultdict(list)
            for read_prop in class_properties_iterable:
                properties_by_class_by_property[class_uri][read_prop.property_uri].append(read_prop)
        return properties_by_class_by_property

    def _read_class_properties_from_graph(self, parent_by_child: dict[URIRef, URIRef]) -> list[_ReadProperties]:
        count_by_type: dict[URIRef, int] = {}
        # Infers all the classes in the graph
        for result_row in self.graph.query(self._ordered_class_query):
            type_uri, instance_count_literal = cast(tuple[URIRef, RdfLiteral], result_row)
            count_by_type[type_uri] = instance_count_literal.toPython()
        if self._rules:
            analysis = RulesAnalysis(self._rules)
            existing_class_properties = {
                (class_entity.suffix, prop.property_): prop
                for class_entity, properties in analysis.properties_by_class(
                    include_ancestors=True, include_different_space=True
                ).items()
                for prop in properties
            }
            existing_classes = {cls_.class_.suffix: cls_ for cls_ in self._rules.classes}
        else:
            existing_class_properties = {}
            existing_classes = {}
        properties_by_class_by_subclass: list[_ReadProperties] = []
        existing_class: InformationClass | None
        total_instance_count = sum(count_by_type.values())
        iterable = count_by_type.items()
        if GLOBAL_CONFIG.use_iterate_bar_threshold and total_instance_count > GLOBAL_CONFIG.use_iterate_bar_threshold:
            iterable = iterate_progress_bar(iterable, len(count_by_type), "Inferring types...")  # type: ignore[assignment]
        for type_uri, instance_count in iterable:
            property_query = self._properties_query.format(type=type_uri, unknown_type=NEAT.UnknownType)
            class_suffix = remove_namespace_from_uri(type_uri)
            if (existing_class := existing_classes.get(class_suffix)) and existing_class.instance_source is None:
                existing_class.instance_source = type_uri

            for result_row in self.graph.query(property_query):
                property_uri, value_type_uri = cast(tuple[URIRef, URIRef], result_row)
                if property_uri == RDF.type:
                    continue
                property_str = remove_namespace_from_uri(property_uri)
                if existing_property := existing_class_properties.get((class_suffix, property_str)):
                    if existing_property.instance_source is None:
                        existing_property.instance_source = [property_uri]
                    elif existing_property.instance_source and property_uri not in existing_property.instance_source:
                        existing_property.instance_source.append(property_uri)
                    continue
                occurrence_query = self._max_occurrence_query.format(type=type_uri, property=property_uri)
                max_occurrence = 1  # default value
                occurrence_row, *_ = list(self.graph.query(occurrence_query))
                if occurrence_row:
                    max_occurrence_literal, *__ = cast(tuple[RdfLiteral, Any], occurrence_row)
                    max_occurrence = int(max_occurrence_literal.toPython())
                properties_by_class_by_subclass.append(
                    _ReadProperties(
                        type_uri=type_uri,
                        property_uri=property_uri,
                        parent_uri=parent_by_child.get(type_uri),
                        value_type=value_type_uri,
                        max_occurrence=max_occurrence,
                        instance_count=instance_count,
                    )
                )
        return properties_by_class_by_subclass

    def _read_parent_by_child_from_graph(self) -> dict[URIRef, URIRef]:
        parent_by_child: dict[URIRef, URIRef] = {}
        for result_row in self.graph.query(self._type_parent_query):
            parent_uri, child_uri = cast(tuple[URIRef, URIRef], result_row)
            parent_by_child[child_uri] = parent_uri
        return parent_by_child

    def _create_property(
        self,
        read_properties: list[_ReadProperties],
        class_suffix: str,
        property_uri: URIRef,
        property_id: str,
        prefixes: dict[str, Namespace],
    ) -> InformationInputProperty:
        first = read_properties[0]
        value_type = self._get_value_type(read_properties, prefixes)
        return InformationInputProperty(
            class_=class_suffix,
            property_=property_id,
            max_count=first.max_occurrence,
            value_type=value_type,
            instance_source=[property_uri],
        )

    def _get_value_type(
        self, read_properties: list[_ReadProperties], prefixes: dict[str, Namespace]
    ) -> str | UnknownEntity:
        value_types = {self.overwrite_data_types.get(prop.value_type, prop.value_type) for prop in read_properties}
        if len(value_types) == 1:
            uri_ref = value_types.pop()
            if uri_ref == NEAT.UnknownType:
                return UnknownEntity()
            self._add_uri_namespace_to_prefixes(uri_ref, prefixes)
            return remove_namespace_from_uri(uri_ref)
        elif len(value_types) == 0:
            return UnknownEntity()
        for uri_ref in value_types:
            self._add_uri_namespace_to_prefixes(uri_ref, prefixes)
        return ", ".join(remove_namespace_from_uri(uri_ref) for uri_ref in value_types)

    def _default_metadata(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        return InformationMetadata(
            space=self.data_model_id.space,
            external_id=self.data_model_id.external_id,
            version=cast(str, self.data_model_id.version),
            name="Inferred Model",
            creator=["NEAT"],
            created=now,
            updated=now,
            description="Inferred model from knowledge graph",
        ).model_dump()
