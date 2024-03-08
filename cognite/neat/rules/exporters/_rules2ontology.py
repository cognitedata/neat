import sys
import warnings
from abc import ABC
from collections import defaultdict
from pathlib import Path
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator
from rdflib import DCTERMS, OWL, RDF, RDFS, XSD, BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection as GraphCollection

from cognite.neat.rules import exceptions
from cognite.neat.rules.models._rules import DMSRules
from cognite.neat.rules.models._rules._types import XSD_VALUE_TYPE_MAPPINGS, EntityTypes
from cognite.neat.rules.models._rules.information_rules import (
    InformationClass,
    InformationMetadata,
    InformationProperty,
    InformationRules,
)
from cognite.neat.utils.utils import generate_exception_report, remove_namespace

from ._base import BaseExporter
from ._validation import are_properties_redefined

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

from cognite.neat.rules._shared import Rules


class GraphExporter(BaseExporter[Graph], ABC):
    def export_to_file(self, filepath: Path, rules: Rules) -> None:
        self.export(rules).serialize(destination=filepath)


class OWLExporter(GraphExporter):
    def export(self, rules: Rules) -> Graph:
        return Ontology.from_rules(rules).as_owl()


class SHACLExporter(GraphExporter):
    def export(self, rules: Rules) -> Graph:
        return Ontology.from_rules(rules).as_shacl()


class SemanticDataModelExporter(GraphExporter):
    def export(self, rules: Rules) -> Graph:
        return Ontology.from_rules(rules).as_semantic_data_model()


class OntologyModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True, strict=False, extra="allow")


class Ontology(OntologyModel):
    """
    Represents an ontology. Thi class is used to generate an OWL ontology from a set of transformation rules.

    Args:
        properties: A list of OWL properties.
        classes: A list of OWL classes.
        shapes: A list of SHACL node shapes.
        metadata: Metadata about the ontology.
        prefixes: A dictionary of prefixes and namespaces.
    """

    properties: list["OWLProperty"]
    classes: list["OWLClass"]
    shapes: list["SHACLNodeShape"]
    metadata: "OWLMetadata"
    prefixes: dict[str, Namespace]

    @classmethod
    def from_rules(cls, input_rules: Rules) -> Self:
        """
        Generates an ontology from a set of transformation rules.

        Args:
            input_rules: The rules to generate the ontology from.

        Returns:
            An instance of Ontology.
        """
        if isinstance(input_rules, InformationRules):
            rules = input_rules
        elif isinstance(input_rules, DMSRules):
            rules = input_rules.as_information_architect_rules()
        else:
            raise ValueError(f"{type(input_rules).__name__} cannot be exported to Ontology")

        properties_redefined, redefinition_warnings = are_properties_redefined(rules, return_report=True)
        if properties_redefined:
            raise exceptions.PropertiesDefinedMultipleTimes(report=generate_exception_report(redefinition_warnings))

        if rules.prefixes is None:
            raise exceptions.PrefixMissing()

        if rules.metadata.namespace is None:
            raise exceptions.MissingDataModelPrefixOrNamespace()

        class_dict = _to_class_dict(rules)
        return cls(
            properties=[
                OWLProperty.from_list_of_properties(definition, rules.metadata.namespace)
                for definition in _to_property_dict(rules).values()
            ],
            classes=[
                OWLClass.from_class(definition, rules.metadata.namespace, rules.prefixes)
                for definition in rules.classes
            ],
            shapes=[
                SHACLNodeShape.from_rules(
                    class_dict[class_],
                    list(properties.values()),
                    rules.metadata.namespace,
                )
                for class_, properties in _to_class_property_pairs(rules).items()
            ]
            + [
                SHACLNodeShape.from_rules(
                    class_,
                    [],
                    rules.metadata.namespace,
                )
                for class_ in class_dict.values()
            ],
            metadata=OWLMetadata(**rules.metadata.model_dump()),
            prefixes=rules.prefixes,
        )

    def as_shacl(self) -> Graph:
        """
        Generates a SHACL graph from the ontology.

        Returns:
            A SHACL graph.
        """

        shacl = Graph()
        shacl.bind(self.metadata.prefix, self.metadata.namespace)
        for prefix, namespace in self.prefixes.items():
            shacl.bind(prefix, namespace)

        for shape in self.shapes:
            for triple in shape.triples:
                shacl.add(triple)  # type: ignore[arg-type]

        return shacl

    def as_owl(self) -> Graph:
        """
        Generates an OWL graph from the ontology.

        Returns:
            An OWL graph.
        """
        owl = Graph()
        owl.bind(self.metadata.prefix, self.metadata.namespace)
        for prefix, namespace in self.prefixes.items():
            owl.bind(prefix, namespace)

        if self.metadata.namespace is None:
            raise exceptions.MetadataSheetNamespaceNotDefined()

        owl.add((URIRef(self.metadata.namespace), RDF.type, OWL.Ontology))
        for property_ in self.properties:
            for triple in property_.triples:
                owl.add(triple)  # type: ignore[arg-type]

        for class_ in self.classes:
            for triple in class_.triples:
                owl.add(triple)  # type: ignore[arg-type]

        for triple in self.metadata.triples:
            owl.add(triple)  # type: ignore[arg-type]

        return owl

    def as_semantic_data_model(self) -> Graph:
        return self.as_owl() + self.as_shacl()

    @property
    def owl_triples(self) -> list[tuple]:
        return list(self.as_owl())

    @property
    def shacl_triples(self) -> list[tuple]:
        return list(self.as_shacl())

    @property
    def triples(self) -> list[tuple]:
        return self.owl_triples + self.shacl_triples

    @property
    def ontology(self) -> str:
        return self.as_owl().serialize()

    @property
    def constraints(self) -> str:
        return self.as_shacl().serialize()

    @property
    def semantic_data_model(self) -> str:
        return (self.as_owl() + self.as_shacl()).serialize()


class OWLMetadata(InformationMetadata):
    @property
    def triples(self) -> list[tuple]:
        # Mandatory triples originating from Metadata mandatory fields
        if self.namespace is None:
            raise exceptions.MetadataSheetNamespaceNotDefined()
        triples: list[tuple] = [
            (URIRef(self.namespace), DCTERMS.hasVersion, Literal(self.version)),
            (URIRef(self.namespace), OWL.versionInfo, Literal(self.version)),
            (URIRef(self.namespace), RDFS.label, Literal(self.name)),
            (URIRef(self.namespace), DCTERMS.title, Literal(self.name)),
            (URIRef(self.namespace), DCTERMS.created, Literal(self.created, datatype=XSD.dateTime)),
            (URIRef(self.namespace), DCTERMS.description, Literal(self.description)),
        ]
        if isinstance(self.creator, list):
            triples.extend([(URIRef(self.namespace), DCTERMS.creator, Literal(creator)) for creator in self.creator])
        else:
            triples.append((URIRef(self.namespace), DCTERMS.creator, Literal(self.creator)))

        # Optional triples originating from Metadata optional fields
        if self.updated:
            triples.append((URIRef(self.namespace), DCTERMS.modified, Literal(self.updated, datatype=XSD.dateTime)))

        return triples


class OWLClass(OntologyModel):
    id_: URIRef
    type_: URIRef = OWL.Class
    label: str | None
    comment: str | None
    sub_class_of: list[URIRef] | None
    namespace: Namespace

    @classmethod
    def from_class(cls, definition: InformationClass, namespace: Namespace, prefixes: dict) -> Self:
        if definition.parent and isinstance(definition.parent, list):
            sub_class_of = []
            for parent_class in definition.parent:
                try:
                    sub_class_of.append(prefixes[parent_class.prefix][parent_class.suffix])
                except KeyError:
                    sub_class_of.append(namespace[parent_class.suffix])
        else:
            sub_class_of = None

        return cls(
            id_=namespace[definition.class_.versioned_id],
            label=definition.name,
            comment=definition.description,
            sub_class_of=sub_class_of,
            namespace=namespace,
        )

    @property
    def type_triples(self) -> list[tuple]:
        return [(self.id_, RDF.type, self.type_)]

    @property
    def label_triples(self) -> list[tuple]:
        if self.label:
            return [(self.id_, RDFS.label, Literal(self.label))]
        else:  # If comment is None, return empty list
            return []

    @property
    def comment_triples(self) -> list[tuple]:
        if self.comment:
            return [(self.id_, RDFS.comment, Literal(self.comment))]
        else:  # If comment is None, return empty list
            return []

    @property
    def subclass_triples(self) -> list[tuple]:
        if self.sub_class_of:
            return [(self.id_, RDFS.subClassOf, sub_class_of) for sub_class_of in self.sub_class_of]
        else:
            return []

    @property
    def triples(self) -> list[tuple]:
        return self.type_triples + self.label_triples + self.comment_triples + self.subclass_triples


class OWLProperty(OntologyModel):
    id_: URIRef
    type_: set[URIRef]
    label: set[str]
    comment: set[str]
    domain: set[URIRef]
    range_: set[URIRef]
    namespace: Namespace

    @staticmethod
    def same_property_id(definitions: list[InformationProperty]) -> bool:
        return len({definition.property_ for definition in definitions}) == 1

    @classmethod
    def from_list_of_properties(cls, definitions: list[InformationProperty], namespace: Namespace) -> "OWLProperty":
        """Here list of properties is a list of properties with the same id, but different definitions."""

        if not cls.same_property_id(definitions):
            raise exceptions.PropertyDefinitionsNotForSameProperty()

        owl_property = cls.model_construct(
            id_=namespace[definitions[0].property_],
            namespace=namespace,
            label=set(),
            comment=set(),
            domain=set(),
            range_=set(),
            type_=set(),
        )
        for definition in definitions:
            owl_property.type_.add(OWL[definition.type_])
            owl_property.range_.add(
                XSD[definition.value_type.suffix]
                if definition.value_type.suffix in XSD_VALUE_TYPE_MAPPINGS
                else namespace[definition.value_type.suffix]
            )
            owl_property.domain.add(namespace[definition.class_.versioned_id])

            if definition.name:
                owl_property.label.add(definition.name)
            if definition.description:
                owl_property.comment.add(definition.description)

        return owl_property

    @field_validator("type_")
    def is_multi_type(cls, v, info: ValidationInfo):
        if len(v) > 1:
            warnings.warn(
                exceptions.OntologyMultiTypeProperty(
                    remove_namespace(info.data["id_"]), [remove_namespace(t) for t in v]
                ).message,
                category=exceptions.OntologyMultiTypeProperty,
                stacklevel=2,
            )
        return v

    @field_validator("range_")
    def is_multi_range(cls, v, info: ValidationInfo):
        if len(v) > 1:
            warnings.warn(
                exceptions.OntologyMultiRangeProperty(
                    remove_namespace(info.data["id_"]), [remove_namespace(t) for t in v]
                ).message,
                category=exceptions.OntologyMultiRangeProperty,
                stacklevel=2,
            )
        return v

    @field_validator("domain")
    def is_multi_domain(cls, v, info: ValidationInfo):
        if len(v) > 1:
            warnings.warn(
                exceptions.OntologyMultiDomainProperty(
                    remove_namespace(info.data["id_"]), [remove_namespace(t) for t in v]
                ).message,
                category=exceptions.OntologyMultiDomainProperty,
                stacklevel=2,
            )
        return v

    @field_validator("label")
    def has_multi_name(cls, v, info: ValidationInfo):
        if len(v) > 1:
            warnings.warn(
                exceptions.OntologyMultiLabeledProperty(remove_namespace(info.data["id_"]), v).message,
                category=exceptions.OntologyMultiLabeledProperty,
                stacklevel=2,
            )
        return v

    @field_validator("comment")
    def has_multi_comment(cls, v, info: ValidationInfo):
        if len(v) > 1:
            warnings.warn(
                exceptions.OntologyMultiDefinitionProperty(remove_namespace(info.data["id_"])).message,
                category=exceptions.OntologyMultiDefinitionProperty,
                stacklevel=2,
            )
        return v

    @property
    def domain_triples(self) -> list[tuple]:
        triples: list[tuple] = []
        if len(self.domain) == 1:
            triples.append((self.id_, RDFS.domain, next(iter(self.domain))))
        else:
            _graph = Graph()
            b_union = BNode()
            b_domain = BNode()
            _graph.add((self.id_, RDFS.domain, b_domain))
            _graph.add((b_domain, OWL.unionOf, b_union))
            _graph.add((b_domain, RDF.type, OWL.Class))
            _ = GraphCollection(_graph, b_union, list(self.domain))
            triples.extend(list(_graph))
        return triples

    @property
    def range_triples(self) -> list[tuple]:
        triples: list[tuple] = []
        if len(self.range_) == 1:
            triples.append((self.id_, RDFS.range, next(iter(self.range_))))
        else:
            _graph = Graph()
            b_union = BNode()
            b_range = BNode()
            _graph.add((self.id_, RDFS.range, b_range))
            _graph.add((b_range, OWL.unionOf, b_union))
            _graph.add((b_range, RDF.type, OWL.Class))
            _graph.add((b_range, OWL.unionOf, b_union))
            _graph.add((b_range, RDF.type, OWL.Class))
            _ = GraphCollection(_graph, b_union, list(self.range_))
            triples.extend(list(_graph))
        return triples

    @property
    def type_triples(self) -> list[tuple]:
        return [(self.id_, RDF.type, type_) for type_ in self.type_]

    @property
    def label_triples(self) -> list[tuple]:
        label = list(filter(None, self.label))
        return [(self.id_, RDFS.label, Literal(label[0] if label else self.id_))]

    @property
    def comment_triples(self) -> list[tuple]:
        return [(self.id_, RDFS.comment, Literal("\n".join(filter(None, self.comment))))]

    @property
    def triples(self) -> list[tuple]:
        return self.type_triples + self.label_triples + self.comment_triples + self.domain_triples + self.range_triples


SHACL = Namespace("http://www.w3.org/ns/shacl#")


class SHACLNodeShape(OntologyModel):
    id_: URIRef
    type_: URIRef = SHACL.NodeShape
    target_class: URIRef
    parent: list[URIRef] | None = None
    property_shapes: list["SHACLPropertyShape"] | None = None
    namespace: Namespace

    @property
    def type_triples(self) -> list[tuple]:
        return [(self.id_, RDF.type, self.type_)]

    @property
    def target_class_triples(self) -> list[tuple]:
        return [(self.id_, SHACL.targetClass, self.target_class)]

    @property
    def target_parent_class_triples(self) -> list[tuple]:
        if self.parent:
            return [(self.id_, RDFS.subClassOf, parent) for parent in self.parent]
        else:
            return []

    @property
    def property_shapes_triples(self) -> list[tuple]:
        triples: list[tuple] = []
        if self.property_shapes:
            for property_shape in self.property_shapes:
                triples.append((self.id_, SHACL.property, property_shape.id_))
                triples.extend(property_shape.triples)
        return triples

    @property
    def triples(self) -> list[tuple]:
        return (
            self.type_triples
            + self.target_class_triples
            + self.property_shapes_triples
            + self.target_parent_class_triples
        )

    @classmethod
    def from_rules(
        cls, class_definition: InformationClass, property_definitions: list[InformationProperty], namespace: Namespace
    ) -> "SHACLNodeShape":
        if class_definition.parent:
            parent = [namespace[parent.suffix + "Shape"] for parent in class_definition.parent]
        else:
            parent = None
        return cls(
            id_=namespace[f"{class_definition.class_}Shape"],
            target_class=namespace[class_definition.class_.versioned_id],
            parent=parent,
            property_shapes=[SHACLPropertyShape.from_property(prop, namespace) for prop in property_definitions],
            namespace=namespace,
        )


class SHACLPropertyShape(OntologyModel):
    id_: BNode
    type_: URIRef = SHACL.property
    path: URIRef  # URIRef to property in OWL
    node_kind: URIRef  # SHACL.IRI or SHACL.Literal
    expected_value_type: URIRef
    min_count: int | None
    max_count: int | None
    namespace: Namespace

    @property
    def path_triples(self) -> list[tuple]:
        return [(self.id_, SHACL.path, self.path)]

    @property
    def node_kind_triples(self) -> list[tuple]:
        triples: list[tuple] = [(self.id_, SHACL.nodeKind, self.node_kind)]

        if self.node_kind == SHACL.Literal:
            triples.append((self.id_, SHACL.datatype, self.expected_value_type))
        else:
            triples.append((self.id_, SHACL.node, self.expected_value_type))

        return triples

    @property
    def cardinality_triples(self) -> list[tuple]:
        triples: list[tuple] = []
        if self.min_count:
            triples.append((self.id_, SHACL.minCount, Literal(self.min_count)))
        if self.max_count:
            triples.append((self.id_, SHACL.maxCount, Literal(self.max_count)))

        return triples

    @property
    def triples(self) -> list[tuple]:
        return self.path_triples + self.node_kind_triples + self.cardinality_triples

    @classmethod
    def from_property(cls, definition: InformationProperty, namespace: Namespace) -> "SHACLPropertyShape":
        return cls(
            id_=BNode(),
            path=namespace[definition.property_],
            node_kind=SHACL.IRI if definition.type_ == EntityTypes.object_property else SHACL.Literal,
            expected_value_type=(
                namespace[f"{definition.value_type.suffix}Shape"]
                if definition.type_ == EntityTypes.object_property
                else XSD[definition.value_type.suffix]
            ),
            min_count=definition.min_count,
            max_count=(
                int(definition.max_count) if definition.max_count and definition.max_count != float("inf") else None
            ),
            namespace=namespace,
        )


def _to_property_dict(rules: InformationRules) -> dict[str, list[InformationProperty]]:
    property_: dict[str, list[InformationProperty]] = defaultdict(list)
    for prop in rules.properties:
        property_[prop.property_].append(prop)
    return property_


def _to_class_dict(rules: InformationRules) -> dict[str, InformationClass]:
    class_: dict[str, InformationClass] = {}
    for cls in rules.classes:
        class_[cls.class_.versioned_id] = cls
    return class_


def _to_class_property_pairs(rules: InformationRules) -> dict[str, dict[str, InformationProperty]]:
    class_property_pairs = {}

    for class_, properties in _get_classes_with_properties(rules).items():
        processed_properties = {}
        for property_ in properties:
            if property_.property_ in processed_properties:
                warnings.warn(
                    "Property has been defined more than once! Only first definition will be considered.", stacklevel=2
                )
                continue

            processed_properties[property_.property_] = property_
        class_property_pairs[class_] = processed_properties

    return class_property_pairs


def _get_classes_with_properties(rules: InformationRules) -> dict[str, list[InformationProperty]]:
    """Returns classes that have been defined in the data model.

    Args:
        transformation_rules: Instance of TransformationRules holding the data model

    Returns:
        Dictionary of classes with a list of properties defined for them
    """

    class_property_pairs: dict[str, list[InformationProperty]] = {}

    for property_ in rules.properties:
        class_ = property_.class_.versioned_id
        if class_ in class_property_pairs:
            class_property_pairs[class_] += [property_]
        else:
            class_property_pairs[class_] = [property_]

    return class_property_pairs
