"""Methods to transform Excel Sheet to Data Model
"""

from rdflib import DCTERMS, OWL, RDFS, SKOS, XSD
from rdflib.graph import RDF, BNode, Collection, Graph, Literal, Namespace, URIRef

from cognite.neat.core.configuration import PREFIXES
from cognite.neat.core.rules.data_model_definitions import DataModelingDefinition
from cognite.neat.core.rules.transformation_rules import Class

SHACL = Namespace("http://www.w3.org/ns/shacl#")


def _wrangle_owl_properties(data_model_definition: DataModelingDefinition) -> dict[str, dict[str, set]]:
    """Wrangles the properties of the data model definition into a dictionary for easier conversion to RDF

    Parameters
    ----------
    data_model_definition : DataModelingDefinition
        Instance of DataModelingDefinition to be wrangled

    Returns
    -------
    dict[str, dict[str, set]]
        Dictionary of properties for easier conversion to RDF
    """
    # TODO: Add support for deprecated, replaced_by, similar_to, equal_to
    properties = {}

    for property_ in data_model_definition.properties.values():
        if property_.property_name != "*":
            if property_.property_name not in properties:
                properties[property_.property_name] = {
                    "domain": {data_model_definition.namespace[property_.class_id]},
                    "range": {
                        data_model_definition.namespace[property_.expected_value_type]
                        if property_.property_type == "ObjectProperty"
                        else XSD[property_.expected_value_type]
                    },
                    "property_type": {
                        OWL[property_.property_type],
                    },
                    "description": {property_.description or None},
                    # "equal_to": {property_.equal_to or None},
                    # "similar_to": {property_.similar_to or None},
                    # "replaced_by": {property_.replaced_by or None},
                    # "deprecated": {property_.deprecated or None},
                }
            else:
                properties[property_.property_name]["domain"].add(data_model_definition.namespace[property_.class_id])
                properties[property_.property_name]["range"].add(
                    data_model_definition.namespace[property_.expected_value_type]
                    if property_.property_type == "ObjectProperty"
                    else XSD[property_.expected_value_type]
                )
                properties[property_.property_name]["property_type"].add(OWL[property_.property_type])
                properties[property_.property_name]["description"].add(property_.description or None)
                # properties[property_.property_name]["equal_to"].add(property_.equal_to or None)
                # properties[property_.property_name]["similar_to"].add(property_.similar_to or None)
                # properties[property_.property_name]["replaced_by"].add(property_.replaced_by or None)
                # properties[property_.property_name]["deprecated"].add(property_.deprecated or None)

    return properties


def _add_ontology_metadata(ontology_graph: Graph, data_model_definition: DataModelingDefinition) -> None:
    """Adds metadata to the ontology graph

    Parameters
    ----------
    ontology_graph : Graph
        Ontology graph to add metadata to
    data_model_definition : DataModelingDefinition
        Instance of DataModelingDefinition to add metadata from
    """
    ontology_graph.add(
        (URIRef(data_model_definition.namespace), DCTERMS.hasVersion, Literal(data_model_definition.metadata.version))
    )
    ontology_graph.add(
        (URIRef(data_model_definition.namespace), OWL.versionInfo, Literal(data_model_definition.metadata.version))
    )
    ontology_graph.add(
        (URIRef(data_model_definition.namespace), RDFS.label, Literal(data_model_definition.metadata.title))
    )
    ontology_graph.add(
        (
            URIRef(data_model_definition.namespace),
            DCTERMS.created,
            Literal(data_model_definition.metadata.created, datatype=XSD.dateTime),
        )
    )
    ontology_graph.add(
        (
            URIRef(data_model_definition.namespace),
            DCTERMS.modified,
            Literal(data_model_definition.metadata.updated, datatype=XSD.dateTime),
        )
    )

    if data_model_definition.metadata.rights:
        ontology_graph.add(
            (URIRef(data_model_definition.namespace), DCTERMS.rights, Literal(data_model_definition.metadata.rights))
        )

    if data_model_definition.metadata.description:
        ontology_graph.add(
            (URIRef(data_model_definition.namespace), RDFS.comment, Literal(data_model_definition.metadata.description))
        )

    if data_model_definition.metadata.creator:
        [
            ontology_graph.add((URIRef(data_model_definition.namespace), DCTERMS.creator, Literal(creator)))
            for creator in data_model_definition.metadata.creator
        ]

    if data_model_definition.metadata.contributor:
        [
            ontology_graph.add((URIRef(data_model_definition.namespace), DCTERMS.contributor, Literal(contributor)))
            for contributor in data_model_definition.metadata.contributor
        ]


def _add_owl_property(
    ontology_graph: Graph, data_model_definition: DataModelingDefinition, properties: dict, property_: str
) -> None:
    """Add OWL property to the ontology graph

    Parameters
    ----------
    ontology_graph : Graph
        Ontology graph to add property to
    data_model_definition : DataModelingDefinition
        Instance of DataModelingDefinition to add property from
    properties : dict
        Wrangled properties
    property_ : str
        Specific property to add to the ontology graph which is a key in the properties dict
    """
    ontology_graph.add((data_model_definition.namespace[property_], RDFS.label, Literal(property_)))

    if len(properties[property_]["description"]) == 1:
        ontology_graph.add(
            (
                data_model_definition.namespace[property_],
                RDFS.comment,
                Literal(list(properties[property_]["description"])[0]),
            )
        )
    else:
        print(f"WARNING: <{property_}> has multiple definitions which will be concatenated")
        ontology_graph.add(
            (
                data_model_definition.namespace[property_],
                RDFS.comment,
                Literal("\n".join(list(properties[property_]["description"]))),
            )
        )

    # add description
    if len(properties[property_]["property_type"]) == 1:
        ontology_graph.add(
            (data_model_definition.namespace[property_], RDF.type, list(properties[property_]["property_type"])[0])
        )
    else:
        print(
            f"BAD PRACTICE: Property <{property_}> is of multiple property types: {', '.join(list(properties[property_]['property_type']))}"
        )
        [
            ontology_graph.add((data_model_definition.namespace[property_], RDF.type, property_type))
            for property_type in properties[property_]["property_type"]
        ]

    if len(properties[property_]["domain"]) == 1:
        ontology_graph.add(
            (data_model_definition.namespace[property_], RDFS.domain, list(properties[property_]["domain"])[0])
        )
    else:
        print(
            f"WARNING: Property <{property_}> domain is union of multiple classes: {', '.join(list(properties[property_]['domain']))}"
        )
        b_union = BNode()
        b_domain = BNode()
        ontology_graph.add((data_model_definition.namespace[property_], RDFS.domain, b_domain))
        ontology_graph.add((b_domain, OWL.unionOf, b_union))
        ontology_graph.add((b_domain, RDF.type, OWL.Class))
        _ = Collection(ontology_graph, b_union, list(properties[property_]["domain"]))

    if len(properties[property_]["range"]) == 1:
        ontology_graph.add(
            (data_model_definition.namespace[property_], RDFS.range, list(properties[property_]["range"])[0])
        )
    else:
        print(
            f"WARNING: Property <{property_}> range is union of multiple types: {', '.join(list(properties[property_]['range']))}"
        )
        b_union = BNode()
        b_range = BNode()
        ontology_graph.add((data_model_definition.namespace[property_], RDFS.range, b_range))
        ontology_graph.add((b_range, OWL.unionOf, b_union))
        ontology_graph.add((b_range, RDF.type, OWL.Class))
        _ = Collection(ontology_graph, b_union, list(properties[property_]["range"]))


def _add_owl_class(ontology_graph: Graph, data_model_definition: DataModelingDefinition, class_: Class) -> None:
    """Add OWL class to ontology graph

    Parameters
    ----------
    ontology_graph : Graph
        Ontology graph
    data_model_definition : DataModelingDefinition
        Instance of DataModelingDefinition class
    class_ : Class
        Class to be added to ontology graph
    """
    # TODO: Simplify by only providing namespace instead of data_model_definition
    ontology_graph.add((data_model_definition.namespace[class_.class_id], RDF.type, OWL.Class))
    ontology_graph.add((data_model_definition.namespace[class_.class_id], RDFS.subClassOf, OWL.Thing))

    # add datatype recognition
    ontology_graph.add((data_model_definition.namespace[class_.class_id], RDFS.label, Literal(class_.class_id)))

    if class_.description:
        ontology_graph.add(
            (data_model_definition.namespace[class_.class_id], RDFS.comment, Literal(class_.description))
        )

    if class_.parent_class:
        ontology_graph.add(
            (
                data_model_definition.namespace[class_.class_id],
                RDFS.subClassOf,
                data_model_definition.namespace[class_.parent_class],
            )
        )

    if class_.deprecated:
        ontology_graph.add(
            (
                data_model_definition.namespace[class_.class_id],
                OWL.deprecated,
                Literal(class_.deprecated, datatype=XSD.boolean),
            )
        )

    if class_.replaced_by:
        ontology_graph.add(
            (
                data_model_definition.namespace[class_.class_id],
                DCTERMS.isReplacedBy,
                data_model_definition.namespace[class_.replaced_by],
            )
        )

    if class_.similar_to:
        ontology_graph.add((data_model_definition.namespace[class_.class_id], SKOS.exactMatch, class_.similar_to))

    if class_.equal_to:
        ontology_graph.add((data_model_definition.namespace[class_.class_id], OWL.equivalentClass, class_.equal_to))


def data_model_definition2owl(
    data_model_definition: DataModelingDefinition,
    prefixes: dict[str, Namespace] = PREFIXES,
    owl_graph: Graph = None,
) -> Graph:
    """Generate OWL ontology from data model definitions

    Parameters
    ----------
    data_model_definition : DataModelingDefinition
        Instance of DataModelingDefinition class
    prefixes : dict[str, Namespace], optional
        Prefixes followed with associated namespaces, by default PREFIXES
    owl_graph : Graph, optional
        ontology graph in case if it is being extended, by default None

    Returns
    -------
    Graph
        OWL ontology based on data model definitions
    """

    if not owl_graph:
        owl_graph = Graph()
        # Bind Data Model namespace and prefix
        owl_graph.bind(data_model_definition.prefix, data_model_definition.namespace)
        # Bind other prefixes and namespaces
        for prefix, namespace in prefixes.items():
            owl_graph.bind(prefix, namespace)

    # add metadata to the graph
    _add_ontology_metadata(owl_graph, data_model_definition)

    # add OWL ontology classes to the graph
    for class_ in data_model_definition.classes.values():
        _add_owl_class(owl_graph, data_model_definition, class_)

    # add OWL ontology properties to the graph
    if owl_properties := _wrangle_owl_properties(data_model_definition):
        for property_ in owl_properties:
            _add_owl_property(owl_graph, data_model_definition, owl_properties, property_)

    return owl_graph


def data_model_definition2shacl(
    data_model_definition: DataModelingDefinition,
    prefixes: dict[str, Namespace] = PREFIXES,
    shacl_graph: Graph = None,
) -> Graph:
    if not shacl_graph:
        shacl_graph = Graph()
        # Bind Data Model namespace and prefix
        shacl_graph.bind(data_model_definition.prefix, data_model_definition.namespace)
        # Bind other prefixes and namespaces
        for prefix, namespace in prefixes.items():
            shacl_graph.bind(prefix, namespace)

    node_shapes = {}
    for shacl_constraint in data_model_definition.properties.values():
        property_name = shacl_constraint.property_name
        if property_name != "*":
            class_id = shacl_constraint.class_id
            node_shape_name = f"{class_id}Shape"

            # adds node shape to shacl graph
            if node_shape_name not in node_shapes:
                node_shapes[node_shape_name] = {}
                shacl_graph.add((data_model_definition.namespace[node_shape_name], RDF.type, SHACL.NodeShape))
                shacl_graph.add(
                    (
                        data_model_definition.namespace[node_shape_name],
                        RDFS.comment,
                        Literal(data_model_definition.classes[class_id].description),
                    )
                )
                shacl_graph.add(
                    (
                        data_model_definition.namespace[node_shape_name],
                        SHACL.targetClass,
                        data_model_definition.namespace[class_id],
                    )
                )

            # adds property shape to shacl graph
            property_shape_node = BNode()
            shacl_graph.add((data_model_definition.namespace[node_shape_name], SHACL.property, property_shape_node))
            shacl_graph.add((property_shape_node, SHACL.path, data_model_definition.namespace[property_name]))
            shacl_graph.add((property_shape_node, SHACL.name, Literal(property_name)))
            if shacl_constraint.property_type == "ObjectProperty":
                shacl_graph.add((property_shape_node, SHACL.nodeKind, SHACL.IRI))
                shacl_graph.add(
                    (
                        property_shape_node,
                        SHACL.node,
                        data_model_definition.namespace[f"{shacl_constraint.expected_value_type}Shape"],
                    )
                )
            else:
                shacl_graph.add((property_shape_node, SHACL.nodeKind, SHACL.Literal))
                shacl_graph.add((property_shape_node, SHACL.datatype, XSD[shacl_constraint.expected_value_type]))

            if shacl_constraint.min_count:
                shacl_graph.add((property_shape_node, SHACL.minCount, Literal(shacl_constraint.min_count)))
            if shacl_constraint.max_count:
                shacl_graph.add((property_shape_node, SHACL.maxCount, Literal(shacl_constraint.max_count)))

    return shacl_graph
