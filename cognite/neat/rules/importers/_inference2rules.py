import re
from datetime import datetime
from pathlib import Path
from typing import Literal, cast, overload

from rdflib import Graph, Namespace, URIRef
from rdflib import Literal as RdfLiteral

import cognite.neat.rules.issues as issues
from cognite.neat.constants import DEFAULT_NAMESPACE, PREFIXES
from cognite.neat.graph.stores import NeatGraphStore
from cognite.neat.rules.importers._base import BaseImporter, Rules, _handle_issues
from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models import InformationRules, RoleTypes
from cognite.neat.rules.models._base import MatchType
from cognite.neat.rules.models.information import (
    InformationMetadata,
    InformationRulesInput,
)
from cognite.neat.utils.utils import get_namespace, remove_namespace, uri_to_short_form

ORDERED_CLASSES_QUERY = """SELECT ?class (count(?s) as ?instances )
                           WHERE { ?s a ?class . }
                           group by ?class order by DESC(?instances)"""

INSTANCES_OF_CLASS_QUERY = """SELECT ?s WHERE { ?s a <class> . }"""

INSTANCE_PROPERTIES_DEFINITION = """SELECT ?property (count(?property) as ?occurrence) ?dataType ?objectType
                                    WHERE {<instance_id> ?property ?value .
                                           BIND(datatype(?value) AS ?dataType)
                                           OPTIONAL {?value rdf:type ?objectType .}}
                                    GROUP BY ?property ?dataType ?objectType"""


class InferenceImporter(BaseImporter):
    """Infers rules from a triple store.

    Rules inference through analysis of knowledge graph provided in various formats.
    Use the factory methods to create an triples store from sources such as
    RDF files, JSON files, YAML files, XML files, or directly from a graph store.

    Args:
        issue_list: Issue list to store issues
        graph: Knowledge graph
        max_number_of_instance: Maximum number of instances to be used in inference
    """

    def __init__(self, issue_list: IssueList, graph: Graph, max_number_of_instance: int = -1):
        self.issue_list = issue_list
        self.graph = graph
        self.max_number_of_instance = max_number_of_instance

    @classmethod
    def from_graph_store(cls, store: NeatGraphStore, max_number_of_instance: int = -1):
        issue_list = IssueList(title="Inferred from graph store")

        return cls(issue_list, store.graph, max_number_of_instance=max_number_of_instance)

    @classmethod
    def from_rdf_file(cls, filepath: Path, max_number_of_instance: int = -1):
        issue_list = IssueList(title=f"'{filepath.name}'")

        graph = Graph()
        try:
            graph.parse(filepath)
        except Exception:
            issue_list.append(issues.fileread.FileReadError(filepath))

        return cls(issue_list, graph, max_number_of_instance=max_number_of_instance)

    @classmethod
    def from_json_file(cls, filepath: Path, max_number_of_instance: int = -1):
        raise NotImplementedError("JSON file format is not supported yet.")

    @classmethod
    def from_yaml_file(cls, filepath: Path, max_number_of_instance: int = -1):
        raise NotImplementedError("YAML file format is not supported yet.")

    @classmethod
    def from_xml_file(cls, filepath: Path, max_number_of_instance: int = -1):
        raise NotImplementedError("JSON file format is not supported yet.")

    @overload
    def to_rules(self, errors: Literal["raise"], role: RoleTypes | None = None) -> Rules: ...

    @overload
    def to_rules(
        self,
        errors: Literal["continue"] = "continue",
        role: RoleTypes | None = None,
    ) -> tuple[Rules | None, IssueList]: ...

    def to_rules(
        self,
        errors: Literal["raise", "continue"] = "continue",
        role: RoleTypes | None = None,
    ) -> tuple[Rules | None, IssueList] | Rules:
        """
        Creates `Rules` object from the data for target role.
        """

        if self.issue_list.has_errors:
            # In case there were errors during the import, the to_rules method will return None
            return self._return_or_raise(self.issue_list, errors)

        rules_dict = self._to_rules_components()

        with _handle_issues(self.issue_list) as future:
            rules: InformationRules
            rules = InformationRulesInput.load(rules_dict).as_rules()

        if future.result == "failure" or self.issue_list.has_errors:
            return self._return_or_raise(self.issue_list, errors)

        return self._to_output(
            rules,
            self.issue_list,
            errors=errors,
            role=role,
        )

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
        prefixes: dict[str, Namespace] = PREFIXES.copy()

        # Adds default namespace to prefixes
        prefixes[self._default_metadata().prefix] = self._default_metadata().namespace

        # Infers all the classes in the graph
        for class_uri, no_instances in self.graph.query(ORDERED_CLASSES_QUERY):  # type: ignore[misc]
            self._add_uri_namespace_to_prefixes(cast(URIRef, class_uri), prefixes)

            if (class_id := remove_namespace(class_uri)) in classes:
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
                    property_id = remove_namespace(property_uri)
                    self._add_uri_namespace_to_prefixes(cast(URIRef, property_uri), prefixes)
                    value_type_uri = data_type_uri if data_type_uri else object_type_uri

                    # this is to skip rdf:type property
                    if not value_type_uri:
                        continue

                    self._add_uri_namespace_to_prefixes(cast(URIRef, value_type_uri), prefixes)
                    value_type_id = remove_namespace(value_type_uri)
                    id_ = f"{class_id}:{property_id}"

                    definition = {
                        "class_": class_id,
                        "property_": property_id,
                        "max_count": cast(RdfLiteral, occurrence).value,
                        "value_type": value_type_id,
                        "reference": property_uri,
                        "transformation": (
                            f"{uri_to_short_form(class_definition['reference'], prefixes)}"
                            f"({uri_to_short_form(cast(URIRef, property_uri), prefixes)})"
                        ),
                        "comment": (
                            f"Class <{class_id}> has property <{property_id}> with "
                            f"value type <{value_type_id}> which occurs <1> times in the graph"
                        ),
                    }

                    # USE CASE 1: If property is not present in properties
                    if id_ not in properties:
                        properties[id_] = definition

                    # USE CASE 2: first time redefinition, value type change to multi
                    elif id_ in properties and definition["value_type"] not in properties[id_]["value_type"]:
                        properties[id_]["value_type"] = properties[id_]["value_type"] + " | " + definition["value_type"]
                        properties[id_]["comment"] = (
                            properties[id_]["comment"] + ", with" + definition["comment"].split("with")[1]
                        )

                    # USE CASE 3: existing but max count is different
                    elif (
                        id_ in properties
                        and definition["value_type"] in properties[id_]["value_type"]
                        and not (properties[id_]["max_count"] == definition["max_count"])
                    ):
                        properties[id_]["max_count"] = max(properties[id_]["max_count"], definition["max_count"])

                        properties[id_]["comment"] = self._update_value_type_occurrence_in_comment(
                            definition["value_type"], properties[id_]["comment"]
                        )

                    # USE CASE 4: Just update the comment with occurrence
                    else:
                        properties[id_]["comment"] = self._update_value_type_occurrence_in_comment(
                            definition["value_type"], properties[id_]["comment"]
                        )

        return {
            "metadata": self._default_metadata().model_dump(),
            "classes": list(classes.values()),
            "properties": list(properties.values()),
            "prefixes": prefixes,
        }

    @classmethod
    def _add_uri_namespace_to_prefixes(cls, URI: URIRef, prefixes: dict[str, Namespace]):
        """Add URI to prefixes dict if not already present

        Args:
            URI: URI from which namespace is being extracted
            prefixes: Dict of prefixes and namespaces
        """
        if Namespace(get_namespace(URI)) not in prefixes.values():
            prefixes[f"prefix-{len(prefixes)+1}"] = Namespace(get_namespace(URI))

    @classmethod
    def _default_metadata(cls):
        return InformationMetadata(
            name="Inferred Model",
            creator="NEAT",
            version="inferred",
            created=datetime.now(),
            updated=datetime.now(),
            description="Inferred model from knowledge graph",
            prefix="inferred",
            namespace=DEFAULT_NAMESPACE,
        )

    @classmethod
    def _update_value_type_occurrence_in_comment(cls, value_type: str, comment: str) -> str:
        occurrence = cls._read_value_type_occurrence_from_comment(value_type, comment)
        return comment.replace(
            f"with value type <{value_type}> which occurs <{occurrence}> times in the graph",
            f"with value type <{value_type}> which occurs <{occurrence+1}> times in the graph",
        )

    @classmethod
    def _read_value_type_occurrence_from_comment(cls, value_type: str, comment: str) -> int:
        return int(
            cast(
                re.Match,
                re.search(
                    rf"with value type <{value_type}> which occurs <(\d+)> times in the graph",
                    comment,
                ),
            ).group(1)
        )
