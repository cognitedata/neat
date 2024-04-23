import logging
from typing import cast

from rdflib import Literal, URIRef

from cognite.neat.legacy.graph.stores import NeatGraphStoreBase


def simple_entity_matcher(
    graph_store: NeatGraphStoreBase,
    source_class: str,
    source_property: str,
    source_value_type: str = "single_value_str",
    target_class: str | None = None,
    target_property: str | None = None,
    relationship_name: str = "link",
    link_direction: str = "target_to_source",  # source_to_target, bidirectional
    matching_method: str = "regexp",  # exact_match, similarity
    link_namespace: str = "http://purl.org/cognite/neat#",
) -> int:
    """simple_entity_matcher performs a simple entity matching between two classes in the graph using
    either exact match or regular expression matching.
    The matching is performed on the values of the source_property and target_property.
    The matching is performed in the direction specified by link_direction.
    The matching_method can be either exact_match or regexp.
    If the source_value_type is multi_value_str, the values are split on comma and added as separate triples.
    Args:
        graph_store (NeatGraphStoreBase): The graph store to perform the matching on and add the links to
        source_class (str): The class of the source entities
        source_property (str): The property of the source entities to match on
        source_value_type (str, optional): The value type of the source property. Defaults to "single_value_str".
        target_class (str | None, optional): The class of the target entities. Defaults to None.
        target_property (str | None, optional): The property of the target entities to match on. Defaults to None.
        relationship_name (str, optional): The name of the relationship to add between the matched entities.
        link_direction (str, optional): The direction of the relationship. Defaults to "target_to_source".
        matching_method (str, optional): The matching method to use. Defaults to "regexp".
    Returns:
        int: The number of new links added to the graph
    """
    if source_value_type == "multi_value_str":
        # Split the values and add them as separate triples
        query = f"""
                    SELECT DISTINCT ?source ?source_value
                    WHERE {{
                        ?source rdf:type neat:{source_class} .
                        ?source neat:{source_property} ?source_value .
                    }}
                """
        triples_to_remove = []
        r1 = cast(tuple, graph_store.query(query))
        result = list(r1)
        for row in result:
            val_split = row[1].split(",")
            if len(val_split) > 1:
                triples_to_remove.append((row[0], URIRef(link_namespace + source_property), row[1]))
                for val in val_split:
                    graph_store.graph.add((row[0], URIRef(link_namespace + source_property), Literal(val)))

        for triple in triples_to_remove:
            graph_store.graph.remove(triple)

    graph_store.graph.commit()
    query = ""
    if matching_method == "exact_match":
        query = f"""
                    SELECT DISTINCT ?source ?target
                    WHERE {{
                        ?source rdf:type neat:{source_class} .
                        ?source neat:{source_property} ?source_value .
                        ?target rdf:type neat:{target_class} .
                        ?target neat:{target_property} ?target_value .
                        FILTER (?source_value = ?target_value)
                    }}
                """
    elif matching_method == "regexp":
        query = f"""
                    SELECT DISTINCT ?source ?target
                    WHERE {{
                        ?source rdf:type neat:{source_class} .
                        ?source neat:{source_property} ?source_value .
                        ?target rdf:type neat:{target_class} .
                        ?target neat:{target_property} ?target_value .
                        FILTER regex(?target_value,?source_value, "i")
                    }}
                """
    else:
        logging.error(f"Unknown matching method {matching_method}")
        return 0
    logging.debug(f"Running matcher query {query}")
    r1 = cast(tuple, graph_store.query(query))
    result = list(r1)
    logging.debug(f"Identified {len(result)} matches from the graph")
    new_links_counter = 0
    for row in result:
        new_links_counter += 1
        if link_direction == "target_to_source":
            graph_store.graph.add((row[1], URIRef(link_namespace + relationship_name), row[0]))
        else:
            graph_store.graph.add((row[0], URIRef(link_namespace + relationship_name), row[1]))

    return new_links_counter
