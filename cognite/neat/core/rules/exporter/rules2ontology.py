from typing import ClassVar, Optional
import warnings
from pydantic import BaseModel, ConfigDict, FieldValidationInfo, field_validator, model_validator
from rdflib import OWL, RDF, RDFS, XSD, DCTERMS, BNode, Graph, Literal, URIRef, Namespace
from rdflib.collection import Collection as GraphCollection

from cognite.neat.core.rules.models import DATA_TYPE_MAPPING, Class, Property, TransformationRules, Metadata
from cognite.neat.core.rules.analysis import to_property_dict, to_class_property_pairs
from cognite.neat.core.rules._validation import are_properties_redefined
from cognite.neat.core.rules import _exceptions
from cognite.neat.core.utils.utils import generate_exception_report, remove_namespace


class OntologyModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True, strict=False, extra="allow")


class Ontology(OntologyModel):
    transformation_rules: TransformationRules
    properties: list["OWLProperty"]
    classes: list["OWLClass"]
    shapes: list["SHACLNodeShape"]
    metadata: "OWLMetadata"

    @field_validator("transformation_rules", mode="before")
    def properties_redefined(cls, rules):
        properties_redefined, redefinition_warnings = are_properties_redefined(rules, return_report=True)
        if properties_redefined:
            raise _exceptions.Error11(report=generate_exception_report(redefinition_warnings))
        return rules

    @model_validator(mode="before")
    def create_shapes(cls, values: dict) -> dict:
        class_property_pairs = to_class_property_pairs(values["transformation_rules"])
        values["shapes"] = [
            SHACLNodeShape.from_rules(
                values["transformation_rules"].classes[class_],
                list(properties.values()),
                values["transformation_rules"].metadata.namespace,
            )
            for class_, properties in class_property_pairs.items()
        ]

        return values

    @model_validator(mode="before")
    def create_classes(cls, values: dict) -> dict:
        values["classes"] = [
            OWLClass.from_class(
                definition,
                values["transformation_rules"].metadata.namespace,
            )
            for definition in values["transformation_rules"].classes.values()
        ]

        return values

    @model_validator(mode="before")
    def create_properties(cls, values: dict) -> dict:
        definitions = to_property_dict(values["transformation_rules"])

        values["properties"] = [
            OWLProperty.from_list_of_properties(
                definition,
                values["transformation_rules"].metadata.namespace,
            )
            for definition in definitions.values()
        ]

        return values

    @model_validator(mode="before")
    def create_metadata(cls, values: dict) -> dict:
        values["metadata"] = OWLMetadata(**values["transformation_rules"].metadata.model_dump())

        return values

    @property
    def shacl(self):
        shacl = Graph()
        shacl.bind(self.transformation_rules.metadata.prefix, self.transformation_rules.metadata.namespace)
        for prefix, namespace in self.transformation_rules.prefixes.items():
            shacl.bind(prefix, namespace)

        for shape in self.shapes:
            for triple in shape.triples:
                shacl.add(triple)

        return shacl

    @property
    def owl(self):
        owl = Graph()
        owl.bind(self.transformation_rules.metadata.prefix, self.transformation_rules.metadata.namespace)
        for prefix, namespace in self.transformation_rules.prefixes.items():
            owl.bind(prefix, namespace)

        owl.add((URIRef(self.transformation_rules.metadata.namespace), RDF.type, OWL.Ontology))
        for property_ in self.properties:
            for triple in property_.triples:
                owl.add(triple)

        for class_ in self.classes:
            for triple in class_.triples:
                owl.add(triple)

        for triple in self.metadata.triples:
            owl.add(triple)

        return owl

    @property
    def owl_triples(self) -> list[tuple]:
        return list(self.owl)

    @property
    def shacl_triples(self) -> list[tuple]:
        return list(self.shacl)

    @property
    def triples(self) -> list[tuple]:
        return self.owl_triples + self.shacl_triples

    @property
    def ontology(self) -> str:
        return self.owl.serialize()

    @property
    def constraints(self) -> str:
        return self.shacl.serialize()

    @property
    def semantic_data_model(self) -> str:
        return (self.owl + self.shacl).serialize()


class OWLMetadata(Metadata):
    @property
    def triples(self) -> list[tuple]:
        # Mandatory triples originating from Metadata mandatory fields
        triples = [
            (URIRef(self.namespace), DCTERMS.hasVersion, Literal(self.version)),
            (URIRef(self.namespace), OWL.versionInfo, Literal(self.version)),
            (URIRef(self.namespace), RDFS.label, Literal(self.title)),
            (URIRef(self.namespace), DCTERMS.title, Literal(self.title)),
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
        if self.rights:
            triples.append((URIRef(self.namespace), DCTERMS.rights, Literal(self.rights)))

        if self.contributor and isinstance(self.contributor, list):
            triples.extend(
                [
                    (URIRef(self.namespace), DCTERMS.contributor, Literal(contributor))
                    for contributor in self.contributor
                ]
            )
        elif self.contributor:
            triples.append((URIRef(self.namespace), DCTERMS.contributor, Literal(self.contributor)))

        return triples


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
        if self.sub_class_of:
            return [(self.id_, RDFS.subClassOf, self.sub_class_of)]
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
    def same_property_id(definitions: list[Property]) -> bool:
        return len({definition.property_id for definition in definitions}) == 1

    @classmethod
    def from_list_of_properties(cls, definitions: list[Property], namespace: Namespace) -> "OWLProperty":
        """Here list of properties is a list of properties with the same id, but different definitions."""

        if not cls.same_property_id(definitions):
            raise _exceptions.Error30()

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

    # TODO: Add warnings to _exceptions.py and use them here:
    @field_validator("type_")
    def is_multi_type(cls, v, info: FieldValidationInfo):
        if len(v) > 1:
            warnings.warn(
                _exceptions.Warning30(remove_namespace(info.data["id_"]), [remove_namespace(t) for t in v]).message,
                category=_exceptions.Warning30,
                stacklevel=2,
            )
        return v

    @field_validator("range_")
    def is_multi_range(cls, v, info: FieldValidationInfo):
        if len(v) > 1:
            warnings.warn(
                _exceptions.Warning31(remove_namespace(info.data["id_"]), [remove_namespace(t) for t in v]).message,
                category=_exceptions.Warning31,
                stacklevel=2,
            )
        return v

    @field_validator("domain")
    def is_multi_domain(cls, v, info: FieldValidationInfo):
        if len(v) > 1:
            warnings.warn(
                _exceptions.Warning32(remove_namespace(info.data["id_"]), [remove_namespace(t) for t in v]).message,
                category=_exceptions.Warning32,
                stacklevel=2,
            )
        return v

    @field_validator("label")
    def has_multi_name(cls, v, info: FieldValidationInfo):
        if len(v) > 1:
            warnings.warn(
                _exceptions.Warning33(remove_namespace(info.data["id_"]), v).message,
                category=_exceptions.Warning33,
                stacklevel=2,
            )
        return v

    @field_validator("comment")
    def has_multi_comment(cls, v, info: FieldValidationInfo):
        if len(v) > 1:
            warnings.warn(
                _exceptions.Warning34(remove_namespace(info.data["id_"])).message,
                category=_exceptions.Warning34,
                stacklevel=2,
            )
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
