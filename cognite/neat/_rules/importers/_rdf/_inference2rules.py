from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import cast

from rdflib import RDF
from rdflib import Literal as RdfLiteral

from cognite.neat._constants import DEFAULT_NAMESPACE
from cognite.neat._issues.warnings import PropertyValueTypeUndefinedWarning
from cognite.neat._rules.models._base_rules import MatchType
from cognite.neat._rules.models.data_types import AnyURI
from cognite.neat._rules.models.entities._single_value import UnknownEntity
from cognite.neat._rules.models.information import (
    InformationMetadata,
)
from cognite.neat._store import NeatGraphStore
from cognite.neat._utils.rdf_ import remove_namespace_from_uri

from ._base import DEFAULT_NON_EXISTING_NODE_TYPE, BaseRDFImporter

ORDERED_CLASSES_QUERY = """SELECT ?class (count(?s) as ?instances )
                           WHERE { ?s a ?class . }
                           group by ?class order by DESC(?instances)"""

INSTANCES_OF_CLASS_QUERY = """SELECT ?s WHERE { ?s a <class> . }"""

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

    Args:
        issue_list: Issue list to store issues
        graph: Knowledge graph
        max_number_of_instance: Maximum number of instances to be used in inference
        prefix: Prefix to be used for the inferred model
    """

    @classmethod
    def from_graph_store(
        cls,
        store: NeatGraphStore,
        prefix: str = "inferred",
        max_number_of_instance: int = -1,
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
    ) -> "InferenceImporter":
        return super().from_graph_store(store, prefix, max_number_of_instance, non_existing_node_type)

    @classmethod
    def from_file(
        cls,
        filepath: Path,
        prefix: str = "inferred",
        max_number_of_instance: int = -1,
        non_existing_node_type: UnknownEntity | AnyURI = DEFAULT_NON_EXISTING_NODE_TYPE,
    ) -> "InferenceImporter":
        return super().from_file(filepath, prefix, max_number_of_instance, non_existing_node_type)

    @classmethod
    def from_json_file(
        cls,
        filepath: Path,
        prefix: str = "inferred",
        max_number_of_instance: int = -1,
    ) -> "InferenceImporter":
        raise NotImplementedError("JSON file format is not supported yet.")

    @classmethod
    def from_yaml_file(
        cls,
        filepath: Path,
        prefix: str = "inferred",
        max_number_of_instance: int = -1,
    ) -> "InferenceImporter":
        raise NotImplementedError("YAML file format is not supported yet.")

    @classmethod
    def from_xml_file(
        cls,
        filepath: Path,
        prefix: str = "inferred",
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
        count_by_value_type_by_property: dict[str, dict[str, int]] = defaultdict(Counter)

        # Infers all the classes in the graph
        for class_uri, no_instances in self.graph.query(ORDERED_CLASSES_QUERY):  # type: ignore[misc]
            if (class_id := remove_namespace_from_uri(class_uri)) in classes:
                # handles cases when class id is already present in classes
                class_id = f"{class_id}_{len(classes)+1}"

            classes[class_id] = {
                "class_": class_id,
                "reference": class_uri,
                "match_type": MatchType.exact,
                "comment": f"Inferred from knowledge graph, where this class has <{no_instances}> instances",
            }

        # Infers all the properties of the class
        for class_id, class_definition in classes.items():
            for (instance,) in self.graph.query(  # type: ignore[misc]
                INSTANCES_OF_CLASS_QUERY.replace("class", class_definition["reference"])
                if self.max_number_of_instance < 0
                else INSTANCES_OF_CLASS_QUERY.replace("class", class_definition["reference"])
                + f" LIMIT {self.max_number_of_instance}"
            ):
                for property_uri, occurrence, data_type_uri, object_type_uri in self.graph.query(  # type: ignore[misc]
                    INSTANCE_PROPERTIES_DEFINITION.replace("instance_id", instance)
                ):  # type: ignore[misc]
                    # this is to skip rdf:type property
                    if property_uri == RDF.type:
                        continue

                    property_id = remove_namespace_from_uri(property_uri)

                    if value_type_uri := (data_type_uri or object_type_uri):
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
                        "reference": property_uri,
                    }

                    count_by_value_type_by_property[id_][value_type_id] += 1

                    # USE CASE 1: If property is not present in properties
                    if id_ not in properties:
                        properties[id_] = definition

                    # USE CASE 2: first time redefinition, value type change to multi
                    elif id_ in properties and definition["value_type"] not in properties[id_]["value_type"]:
                        properties[id_]["value_type"] = properties[id_]["value_type"] + " | " + definition["value_type"]

                    # USE CASE 3: existing but max count is different
                    elif (
                        id_ in properties
                        and definition["value_type"] in properties[id_]["value_type"]
                        and properties[id_]["max_count"] != definition["max_count"]
                    ):
                        properties[id_]["max_count"] = max(properties[id_]["max_count"], definition["max_count"])

        # Add comments
        for id_, property_ in properties.items():
            if id_ not in count_by_value_type_by_property:
                continue

            count_by_value_type = count_by_value_type_by_property[id_]
            count_list = sorted(count_by_value_type.items(), key=lambda item: item[1], reverse=True)
            # Make the comment more readable by adapting to the number of value types
            base_string = "<{value_type}> which occurs <{count}> times"
            if len(count_list) == 1:
                type_, count = count_list[0]
                counts_str = f"with value type {base_string.format(value_type=type_, count=count)} in the graph"
            elif len(count_list) == 2:
                first = base_string.format(value_type=count_list[0][0], count=count_list[0][1])
                second = base_string.format(value_type=count_list[1][0], count=count_list[1][1])
                counts_str = f"with value types {first} and {second} in the graph"
            else:
                first_part = ", ".join(
                    base_string.format(value_type=type_, count=count) for type_, count in count_list[:-1]
                )
                last = base_string.format(value_type=count_list[-1][0], count=count_list[-1][1])
                counts_str = f"with value types {first_part} and {last} in the graph"

            class_id = property_["class_"]
            property_id = property_["property_"]
            property_["comment"] = f"Class <{class_id}> has property <{property_id}> {counts_str}"

        return {
            "metadata": self._default_metadata().model_dump(),
            "classes": list(classes.values()),
            "properties": list(properties.values()),
        }

    def _default_metadata(self):
        return InformationMetadata(
            name="Inferred Model",
            creator="NEAT",
            version="inferred",
            created=datetime.now(),
            updated=datetime.now(),
            description="Inferred model from knowledge graph",
            prefix=self.prefix,
            namespace=DEFAULT_NAMESPACE,
        )
