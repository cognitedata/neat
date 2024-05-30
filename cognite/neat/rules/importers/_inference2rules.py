from datetime import datetime
from pathlib import Path
from typing import Literal, cast, overload

from rdflib import Graph, Namespace, URIRef
from rdflib import Literal as RdfLiteral

import cognite.neat.rules.issues as issues
from cognite.neat.constants import PREFIXES
from cognite.neat.rules.importers._base import BaseImporter, Rules, _handle_issues
from cognite.neat.rules.issues import IssueList
from cognite.neat.rules.models import InformationRules, RoleTypes
from cognite.neat.rules.models._base import MatchType
from cognite.neat.rules.models.entities import ClassEntity
from cognite.neat.rules.models.information import (
    InformationMetadata,
    InformationRulesInput,
)
from cognite.neat.utils.utils import get_namespace, remove_namespace, replace_non_alphanumeric_with_underscore

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
    """Rules inference through analysis of knowledge graph provided in various formats.

    Args:
        issue_list: Issue list to store issues
        graph: Knowledge graph
        max_number_of_instance: Maximum number of instances to be used in inference
        make_compliant: If True, NEAT will attempt to make the imported rules compliant with CDF
    """

    def __init__(
        self, issue_list: IssueList, graph: Graph, max_number_of_instance: int = -1, make_compliant: bool = False
    ):
        self.issue_list = issue_list
        self.graph = graph
        self.max_number_of_instance = max_number_of_instance
        self.make_compliant = make_compliant

    @classmethod
    def from_rdf_file(cls, filepath: Path, make_compliant: bool = False, max_number_of_instance: int = -1):
        issue_list = IssueList(title=f"'{filepath.name}'")

        graph = Graph()
        try:
            graph.parse(filepath)
        except Exception:
            issue_list.append(issues.fileread.FileReadError(filepath))

        return cls(issue_list, graph, make_compliant=make_compliant, max_number_of_instance=max_number_of_instance)

    @classmethod
    def from_json_file(cls, filepath: Path, make_compliant: bool = False, max_number_of_instance: int = -1):
        raise NotImplementedError("JSON file format is not supported yet.")

    @classmethod
    def from_yaml_file(cls, filepath: Path, make_compliant: bool = False, max_number_of_instance: int = -1):
        raise NotImplementedError("YAML file format is not supported yet.")

    @classmethod
    def from_xml_file(cls, filepath: Path, make_compliant: bool = False, max_number_of_instance: int = -1):
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
        self, errors: Literal["raise", "continue"] = "continue", role: RoleTypes | None = None
    ) -> tuple[Rules | None, IssueList] | Rules:
        """
        Creates `Rules` object from the data for target role.
        """

        if self.issue_list.has_errors:
            # In case there were errors during the import, the to_rules method will return None
            return self._return_or_raise(self.issue_list, errors)

        rules_dict = self._to_rules_components()

        # adding additional prefix
        rules_dict["prefixes"][rules_dict["metadata"]["prefix"]] = rules_dict["metadata"]["namespace"]

        with _handle_issues(self.issue_list) as future:
            rules: InformationRules
            rules = InformationRulesInput.load(rules_dict).as_rules()

        if future.result == "failure" or self.issue_list.has_errors:
            return self._return_or_raise(self.issue_list, errors)

        if self.make_compliant and rules:
            self._make_dms_compliant_rules(rules)

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
        prefixes: dict[str, Namespace] = PREFIXES

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
                "comment": f"Inferred from knowledge graph, where this class has {no_instances} instances",
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
                    id_ = f"{class_id}:{property_id}:{value_type_id}"

                    definition = {
                        "class_": class_id,
                        "property_": property_id,
                        "max_count": cast(RdfLiteral, occurrence).value,
                        "value_type": value_type_id,
                        "reference": property_uri,
                    }

                    # USE CASE 1: If property is not present in properties
                    if id_ not in properties:
                        properties[id_] = definition
                    # USE CASE 2: If property is present in properties but with different max count
                    elif id_ in properties and not (properties[id_]["max_count"] == definition["max_count"]):
                        properties[id_]["max_count"] = max(properties[id_]["max_count"], definition["max_count"])

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
            namespace="http://purl.org/cognite/neat/inferred/",
        )

    @classmethod
    def _make_dms_compliant_rules(cls, rules: InformationRules) -> InformationRules:
        cls._fix_property_redefinition(rules)
        cls._fix_naming_of_entities(rules)

    @classmethod
    def _fix_property_redefinition(cls, rules: InformationRules) -> InformationRules:
        viewed = set()
        for i, property_ in enumerate(rules.properties.data):
            prop_id = f"{property_.class_}.{property_.property_}"
            if prop_id in viewed:
                property_.property_ = f"{property_.property_}_{i+1}"
                viewed.add(f"{property_.class_}.{property_.property_}")
            else:
                viewed.add(prop_id)

    @classmethod
    def _fix_naming_of_entities(cls, rules: InformationRules) -> InformationRules:

        # Fixing class ids
        for class_ in rules.classes:
            class_.class_ = class_.class_.as_dms_compliant_entity()
            class_.parent = [parent.as_dms_compliant_entity() for parent in class_.parent] if class_.parent else None

        # Fixing property definitions
        for property_ in rules.properties:

            # fix class id
            property_.class_ = property_.class_.as_dms_compliant_entity()

            # fix property id
            property_.property_ = replace_non_alphanumeric_with_underscore(property_.property_)

            # fix value type
            if isinstance(property_.value_type, ClassEntity):
                property_.value_type = property_.value_type.as_dms_compliant_entity()
