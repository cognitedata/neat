import sys
import warnings
from abc import ABC
from pathlib import Path
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator
from rdflib import DCTERMS, OWL, RDF, RDFS, XSD, BNode, Graph, Literal, Namespace, URIRef
from rdflib.collection import Collection as GraphCollection

from cognite.neat.v0.core._constants import DEFAULT_NAMESPACE as NEAT_NAMESPACE
from cognite.neat.v0.core._data_model._constants import EntityTypes
from cognite.neat.v0.core._data_model.analysis import DataModelAnalysis
from cognite.neat.v0.core._data_model.models.conceptual import (
    Concept,
    ConceptualDataModel,
    ConceptualMetadata,
    ConceptualProperty,
)
from cognite.neat.v0.core._data_model.models.data_types import DataType
from cognite.neat.v0.core._data_model.models.entities import ConceptEntity
from cognite.neat.v0.core._issues.errors import (
    PropertyDefinitionDuplicatedError,
)
from cognite.neat.v0.core._issues.warnings import PropertyDefinitionDuplicatedWarning
from cognite.neat.v0.core._utils.rdf_ import remove_namespace_from_uri

from ._base import BaseExporter

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

SHACL = Namespace("http://www.w3.org/ns/shacl#")


class GraphExporter(BaseExporter[ConceptualDataModel, Graph], ABC):
    def export_to_file(self, data_model: ConceptualDataModel, filepath: Path) -> None:
        self.export(data_model).serialize(destination=filepath, encoding=self._encoding, newline=self._new_line)


class OWLExporter(GraphExporter):
    """Exports verified conceptual data model to an OWL ontology."""

    def export(self, data_model: ConceptualDataModel) -> Graph:
        return Ontology.from_data_model(data_model).graph

    @property
    def description(self) -> str:
        return "Export verified conceptual data model to OWL."


class SHACLExporter(GraphExporter):
    """Exports data_model to a SHACL graph."""

    def export(self, data_model: ConceptualDataModel) -> Graph:
        return ShaclShapes.from_data_model(data_model).graph

    @property
    def description(self) -> str:
        return "Export verified conceptual data model to SHACL."


class _ModelConfig(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(arbitrary_types_allowed=True, strict=False, extra="allow")


class Ontology(_ModelConfig):
    """
    Represents an ontology. This class is used to generate an OWL ontology from conceptual data model.

    Args:
        properties: A list of OWL properties.
        classes: A list of OWL classes.
        metadata: Metadata about the ontology.
        prefixes: A dictionary of prefixes and namespaces.
    """

    metadata: "OWLMetadata"
    properties: list["OWLProperty"]
    classes: list["OWLClass"]
    prefixes: dict[str, Namespace]

    @classmethod
    def from_data_model(cls, data_model: ConceptualDataModel) -> Self:
        """
        Generates an ontology from a set of transformation data_model.

        Args:
            data_model: The data_model to generate the ontology from.

        Returns:
            An instance of Ontology.
        """
        analysis = DataModelAnalysis(data_model)
        return cls(
            properties=[
                OWLProperty.from_list_of_properties(definition, data_model.metadata.namespace)
                for definition in analysis.property_by_id().values()
            ],
            classes=[
                OWLClass.from_concept(definition, data_model.metadata.namespace, data_model.prefixes)
                for definition in data_model.concepts
            ],
            metadata=OWLMetadata(**data_model.metadata.model_dump()),
            prefixes=data_model.prefixes,
        )

    @property
    def graph(self) -> Graph:
        """
        Generates an OWL graph from the ontology.

        Returns:
            An OWL graph.
        """
        owl = Graph()
        owl.bind(self.metadata.prefix, self.metadata.namespace)
        for prefix, namespace in self.prefixes.items():
            owl.bind(prefix, namespace)

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


class OWLMetadata(ConceptualMetadata):
    @property
    def triples(self) -> list[tuple]:
        # Mandatory triples originating from Metadata mandatory fields
        triples: list[tuple] = [
            (URIRef(self.namespace), DCTERMS.hasVersion, Literal(self.version)),
            (URIRef(self.namespace), OWL.versionInfo, Literal(self.version)),
            (URIRef(self.namespace), RDFS.label, Literal(self.name)),
            (URIRef(self.namespace), NEAT_NAMESPACE.prefix, Literal(self.prefix)),
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


class OWLClass(_ModelConfig):
    id_: URIRef
    type_: URIRef = OWL.Class
    label: str | None
    comment: str | None
    sub_class_of: list[URIRef] | None
    namespace: Namespace

    @classmethod
    def from_concept(cls, definition: Concept, namespace: Namespace, prefixes: dict) -> Self:
        if definition.implements and isinstance(definition.implements, list):
            sub_class_of = []
            for parent_class in definition.implements:
                try:
                    sub_class_of.append(prefixes[str(parent_class.prefix)][str(parent_class.suffix)])
                except KeyError:
                    sub_class_of.append(namespace[str(parent_class.suffix)])
        else:
            sub_class_of = None

        return cls(
            id_=namespace[str(definition.concept.suffix)],
            label=definition.name if definition.name else None,
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
    def title_triples(self) -> list[tuple]:
        if self.label:
            return [
                (
                    self.id_,
                    DCTERMS.title,
                    Literal(f"{remove_namespace_from_uri(self.id_)} - {self.label}"),
                )
            ]
        else:
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
        return (
            self.type_triples + self.label_triples + self.title_triples + self.comment_triples + self.subclass_triples
        )


class OWLProperty(_ModelConfig):
    id_: URIRef
    type_: set[URIRef]
    label: set[str]
    comment: set[str]
    domain: set[URIRef]
    range_: set[URIRef]
    namespace: Namespace

    @classmethod
    def from_list_of_properties(cls, definitions: list[ConceptualProperty], namespace: Namespace) -> "OWLProperty":
        """Here list of properties is a list of properties with the same id, but different definitions."""
        property_ids = {definition.property_ for definition in definitions}
        if len(property_ids) != 1:
            raise PropertyDefinitionDuplicatedError(
                definitions[0].concept,
                "class",
                definitions[0].property_,
                frozenset(property_ids),
            )

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

            if isinstance(definition.value_type, DataType):
                owl_property.range_.add(XSD[definition.value_type.xsd])
            elif isinstance(definition.value_type, ConceptEntity):
                owl_property.range_.add(namespace[str(definition.value_type.suffix)])
            else:
                raise ValueError(f"Value type {definition.value_type.type_} is not supported")
            owl_property.domain.add(namespace[str(definition.concept.suffix)])
            if definition.name:
                owl_property.label.add(definition.name)
            if definition.description:
                owl_property.comment.add(definition.description)

        return owl_property

    @field_validator("type_")
    def is_multi_type(cls, v: Any, info: ValidationInfo) -> Any:
        if len(v) > 1:
            warnings.warn(
                PropertyDefinitionDuplicatedWarning(
                    remove_namespace_from_uri(info.data["id"]),
                    "class",
                    "type",
                    frozenset({remove_namespace_from_uri(t) for t in v}),
                    "This warning occurs when a same property is define for two object/classes where"
                    " its expected value type is different in one definition, e.g. acts as an edge, while in "
                    "other definition acts as and attribute",
                    "If a property takes different value types for different objects, simply define new property",
                ),
                stacklevel=2,
            )
        return v

    @field_validator("range_")
    def is_multi_range(cls, v: Any, info: ValidationInfo) -> Any:
        if len(v) > 1:
            warnings.warn(
                PropertyDefinitionDuplicatedWarning(
                    remove_namespace_from_uri(info.data["id_"]),
                    "class",
                    "range",
                    frozenset({remove_namespace_from_uri(t) for t in v}),
                    "This warning occurs when a property takes range of "
                    "values which consists of union of multiple value types.",
                    "If value types for different objects, simply define new property",
                ),
                stacklevel=2,
            )
        return v

    @field_validator("domain")
    def is_multi_domain(cls, v: Any, info: ValidationInfo) -> Any:
        if len(v) > 1:
            warnings.warn(
                PropertyDefinitionDuplicatedWarning(
                    remove_namespace_from_uri(info.data["id_"]),
                    "class",
                    "domain",
                    frozenset({remove_namespace_from_uri(t) for t in v}),
                    "This warning occurs when a same property is define for two object/classes where"
                    " its expected value type is different in one definition, e.g. acts as an edge, while in "
                    "other definition acts as and attribute",
                    "If value types for different objects, simply define new property",
                ),
                stacklevel=2,
            )
        return v

    @field_validator("label")
    def has_multi_name(cls, v: Any, info: ValidationInfo) -> Any:
        if len(v) > 1:
            warnings.warn(
                PropertyDefinitionDuplicatedWarning(
                    remove_namespace_from_uri(info.data["id_"]),
                    "class",
                    "label",
                    frozenset(v),
                    f"Only the first label (name) will be used, {v[0]}",
                ),
                stacklevel=2,
            )
        return v

    @field_validator("comment")
    def has_multi_comment(cls, v: Any, info: ValidationInfo) -> Any:
        if len(v) > 1:
            warnings.warn(
                PropertyDefinitionDuplicatedWarning(
                    remove_namespace_from_uri(info.data["id_"]),
                    "class",
                    "comment",
                    frozenset(v),
                    "All definitions will be concatenated to form a single definition.",
                ),
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
        if label := list(filter(None, self.label)):
            return [(self.id_, RDFS.label, Literal(label[0]))]
        else:
            return []

    @property
    def title_triples(self) -> list[tuple]:
        if label := list(filter(None, self.label)):
            return [
                (
                    self.id_,
                    DCTERMS.title,
                    Literal(f"{remove_namespace_from_uri(self.id_)} - {label[0]}"),
                )
            ]
        else:
            return []

    @property
    def comment_triples(self) -> list[tuple]:
        return [(self.id_, RDFS.comment, Literal("\n".join(filter(None, self.comment))))]

    @property
    def triples(self) -> list[tuple]:
        return (
            self.type_triples
            + self.label_triples
            + self.title_triples
            + self.comment_triples
            + self.domain_triples
            + self.range_triples
        )


class ShaclShapes(_ModelConfig):
    """
    Represents a SHACL shapes. This class is used to generate a SHACL graph from conceptual data model.

    Args:
        shapes: A list of SHACL node shapes.
        prefixes: A dictionary of prefixes and namespaces.
    """

    shapes: list["SHACLNodeShape"]
    prefixes: dict[str, Namespace]

    @classmethod
    def from_data_model(cls, data_model: ConceptualDataModel) -> Self:
        """
        Generates shacl shapes from a conceptual data model.

        Args:
            data_model: The data_model to generate the shacl shapes from.

        Returns:
            An instance of ShaclShapes.
        """
        analysis = DataModelAnalysis(data_model)
        concepts_by_concept_entity = analysis.concept_by_concept_entity
        properties_by_concept_entity = analysis.properties_by_concepts()
        return cls(
            shapes=[
                # shapes that have property shapes as well
                SHACLNodeShape.from_concept(
                    concept_entity,
                    concepts_by_concept_entity,
                    properties,
                    data_model.metadata.namespace,
                )
                for concept_entity, properties in properties_by_concept_entity.items()
            ]
            + [
                # shapes without any property shapes
                SHACLNodeShape.from_concept(
                    concept_entity,
                    concepts_by_concept_entity,
                    [],
                    data_model.metadata.namespace,
                )
                for concept_entity in concepts_by_concept_entity.keys()
                if concept_entity not in properties_by_concept_entity
            ],
            prefixes=data_model.prefixes,
        )

    @property
    def graph(self) -> Graph:
        """
        Generates a SHACL graph from the class instance.

        Returns:
            A SHACL graph.
        """

        shacl = Graph()
        for prefix, namespace in self.prefixes.items():
            shacl.bind(prefix, namespace)

        for shape in self.shapes:
            for triple in shape.triples:
                shacl.add(triple)  # type: ignore[arg-type]

        return shacl


class SHACLNodeShape(_ModelConfig):
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
    def from_concept(
        cls,
        concept_entity: ConceptEntity,
        concepts_by_concept_entity: dict[ConceptEntity, Concept],
        properties: list[ConceptualProperty],
        namespace: Namespace,
    ) -> "SHACLNodeShape":
        if not (concept := concepts_by_concept_entity.get(concept_entity)):
            raise ValueError(f"Concept {concept_entity} not found in data model!")

        if concept.implements:
            parent = [namespace[str(parent.suffix) + "Shape"] for parent in concept.implements]
        else:
            parent = None
        return cls(
            id_=namespace[f"{concept.concept.suffix!s}Shape"],
            target_class=concept.instance_source or namespace[str(concept.concept.suffix)],
            parent=parent,
            property_shapes=[
                SHACLPropertyShape.from_property(property_, concepts_by_concept_entity, namespace)
                for property_ in properties
            ],
            namespace=namespace,
        )


class SHACLPropertyShape(_ModelConfig):
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
    def from_property(
        cls,
        property_: ConceptualProperty,
        concepts_by_concept_entity: dict[ConceptEntity, Concept],
        namespace: Namespace,
    ) -> "SHACLPropertyShape":
        if isinstance(property_.value_type, ConceptEntity):
            concept = concepts_by_concept_entity.get(property_.value_type)
            value_type_uri = concept.instance_source if concept else None
            expected_value_type = value_type_uri or namespace[f"{property_.value_type.suffix}"]
        elif isinstance(property_.value_type, DataType):
            expected_value_type = XSD[property_.value_type.xsd]
        else:
            raise NotImplementedError(f"Value type {property_.value_type.type_} is not supported yet")

        return cls(
            id_=BNode(),
            path=property_.instance_source[0]
            if property_.instance_source and len(property_.instance_source) == 1
            else namespace[property_.property_],
            node_kind=SHACL.IRI if property_.type_ == EntityTypes.object_property else SHACL.Literal,
            expected_value_type=expected_value_type,
            min_count=property_.min_count,
            max_count=(
                int(property_.max_count) if property_.max_count and property_.max_count != float("inf") else None
            ),
            namespace=namespace,
        )
