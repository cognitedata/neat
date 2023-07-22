from logging import warn
from typing import ClassVar, Optional
from pydantic import BaseModel, ConfigDict, field_validator
from rdflib import OWL, RDF, RDFS, XSD, BNode, Graph, Literal, URIRef, Namespace
from rdflib.collection import Collection as GraphCollection

from cognite.neat.core.rules.models import DATA_TYPE_MAPPING, Class, Property, TransformationRules
from cognite.neat.core.rules._validation import are_properties_redefined
from cognite.neat.core.rules import _exceptions
from cognite.neat.core.utils.utils import generate_exception_report


class OntologyModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True, strict=False, extra="allow")


class Ontology(OntologyModel):
    transformation_rules: TransformationRules
    properties: list["OWLProperty"]  # these should be created from transformation rules, mode = after
    classes: list["OWLClass"]  # these should be created from transformation rules, mode = after
    shapes: list["SHACLNodeShape"]  # these should be created from transformation rules, mode = after

    @field_validator("transformation_rules", mode="before")
    def properties_redefined(cls, rules):
        properties_redefined, redefinition_warnings = are_properties_redefined(rules, return_report=True)
        if properties_redefined:
            raise _exceptions.Error11(report=generate_exception_report(redefinition_warnings))
        return rules

    @property
    def owl(self, serialization="turtle") -> str:
        ...

    # creates graph, binds namespaces, adds triples from classes and properties
    # return serialized graph as string

    @property
    def shacl(self, serialization="turtle") -> str:
        ...

    # creates graph, binds namespaces, adds triples from shapes
    # return serialized graph as string


class OWLClass(OntologyModel):
    id_: URIRef
    type_: URIRef = OWL.Class
    label: Optional[str]
    comment: Optional[str]
    sub_class_of: Optional[URIRef]
    namespace: Namespace

    @classmethod
    def from_class(cls, definition: Class, namespace: Namespace) -> "OWLClass":
        class_dict = {
            "id_": namespace[definition.class_id],
            "label": definition.class_name,
            "comment": definition.description,
            "sub_class_of": namespace[definition.parent_class] if definition.parent_class else None,
        }

        return cls(**class_dict, namespace=namespace)

    @property
    def type_triples(self) -> list[tuple]:
        return [(self.id_, RDF.type, self.type_)]

    @property
    def label_triples(self) -> list[tuple]:
        return [(self.id_, RDFS.label, Literal(self.label))]

    @property
    def comment_triples(self) -> list[tuple]:
        return [(self.id_, RDFS.comment, Literal(self.comment))]

    @property
    def subclass_triples(self) -> list[tuple]:
        return [(self.id_, RDFS.subClassOf, self.sub_class_of)]

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
    def same_property_id(definitions: list[Property]) -> bool:
        return len({definition.property_id for definition in definitions}) == 1

    @classmethod
    def from_list_of_properties(cls, definitions: list[Property], namespace: Namespace) -> "OWLProperty":
        """Here list of properties is a list of properties with the same id, but different definitions."""

        if not cls.same_property_id(definitions):
            raise ValueError("All definitions should have the same property_id! Aborting.")

        prop_dict = {
            "id_": namespace[definitions[0].property_id],
            "type_": set(),
            "label": set(),
            "comment": set(),
            "domain": set(),
            "range_": set(),
        }

        for definition in definitions:
            prop_dict["type_"].add(OWL[definition.property_type])
            prop_dict["range_"].add(
                XSD[definition.expected_value_type]
                if definition.expected_value_type in DATA_TYPE_MAPPING
                else namespace[definition.expected_value_type]
            )
            prop_dict["domain"].add(namespace[definition.class_id])

            if definition.property_name:
                prop_dict["label"].add(definition.property_name)
            if definition.description:
                prop_dict["comment"].add(definition.description)

        return cls(**prop_dict, namespace=namespace)

    @field_validator("type_")
    def is_multy_type(cls, v):
        if len(v) > 1:
            warn(
                (
                    "It is bad practice that property of multiple types. "
                    f"Currently it defined as multi type property: {', '.join(filter(None, v))}"
                )
            )
        return v

    @field_validator("range_")
    def is_multi_range(cls, v):
        if len(v) > 1:
            warn(
                (
                    "Property should ideally have only single range of values."
                    f" Currently it has multiple ranges {', '.join(filter(None, v))}"
                )
            )
        return v

    @field_validator("domain")
    def is_multi_domain(cls, v):
        if len(v) > 1:
            warn(
                (
                    f"Property should ideally be defined for single class."
                    f" Currently it has multiple ranges {', '.join(filter(None, v))}"
                )
            )
        return v

    @field_validator("label")
    def has_multi_name(cls, v):
        if len(v) > 1:
            warn(
                (
                    "Property should have single preferred label (human readable name)."
                    f" Currently it has multiple labels {', '.join(filter(None, v))}."
                    " First one will be used as preferred label."
                )
            )
        return v

    @field_validator("comment")
    def has_multi_comment(cls, v):
        if len(v) > 1:
            warn("Multiple definitions (aka comments) of property detected. Definitions will be concatenated.")
        return v

    @property
    def domain_triples(self) -> list[tuple]:
        triples = []
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
        triples = []
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
    property_shapes: list["SHACLPropertyShape"]
    namespace: Namespace

    @property
    def type_triples(self) -> list[tuple]:
        return [(self.id_, RDF.type, self.type_)]

    @property
    def target_class_triples(self) -> list[tuple]:
        return [(self.id_, SHACL.targetClass, self.target_class)]

    @property
    def property_shapes_triples(self) -> list[tuple]:
        triples = []
        for property_shape in self.property_shapes:
            triples.append((self.id_, SHACL.property, property_shape.id_))
            triples.extend(property_shape.triples)
        return triples

    @property
    def triples(self) -> list[tuple]:
        return self.type_triples + self.target_class_triples + self.property_shapes_triples

    @classmethod
    def from_rules(
        cls, class_definition: Class, property_definitions: list[Property], namespace: Namespace
    ) -> "SHACLNodeShape":
        node_dict = {
            "id_": namespace[f"{class_definition.class_id}Shape"],
            "target_class": namespace[class_definition.class_id],
            "property_shapes": [SHACLPropertyShape.from_property(prop, namespace) for prop in property_definitions],
        }

        return cls(**node_dict, namespace=namespace)


class SHACLPropertyShape(OntologyModel):
    id_: BNode
    type_: URIRef = SHACL.property
    path: URIRef  # URIRef to property in OWL
    node_kind: URIRef  # SHACL.IRI or SHACL.Literal
    expected_value_type: URIRef
    min_count: Optional[int]
    max_count: Optional[int]
    namespace: Namespace

    @property
    def path_triples(self) -> list[tuple]:
        return [(self.id_, SHACL.path, self.path)]

    @property
    def node_kind_triples(self) -> list[tuple]:
        triples = [(self.id_, SHACL.nodeKind, self.node_kind)]

        if self.node_kind == SHACL.Literal:
            triples.append((self.id_, SHACL.datatype, self.expected_value_type))
        else:
            triples.append((self.id_, SHACL.node, self.expected_value_type))

        return triples

    @property
    def cardinality_triples(self) -> list[tuple]:
        triples = []
        if self.min_count:
            triples.append((self.id_, SHACL.minCount, Literal(self.min_count)))
        if self.max_count:
            triples.append((self.id_, SHACL.maxCount, Literal(self.max_count)))

        return triples

    @property
    def triples(self) -> list[tuple]:
        return self.path_triples + self.node_kind_triples + self.cardinality_triples

    @classmethod
    def from_property(cls, definition: Property, namespace: Namespace) -> "SHACLPropertyShape":
        prop_dict = {
            "id_": BNode(),
            "path": namespace[definition.property_id],
            "node_kind": SHACL.IRI if definition.property_type == "ObjectProperty" else SHACL.Literal,
            "expected_value_type": (
                namespace[f"{definition.expected_value_type}Shape"]
                if definition.property_type == "ObjectProperty"
                else XSD[definition.expected_value_type]
            ),
            "min_count": definition.min_count,
            "max_count": definition.max_count,
        }

        return cls(**prop_dict, namespace=namespace)
