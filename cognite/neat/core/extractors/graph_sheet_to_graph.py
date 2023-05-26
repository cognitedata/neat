import logging
import warnings

import pandas as pd
from rdflib import RDF, Graph, Literal

from cognite.neat.core.data_classes.transformation_rules import TransformationRules


def sheet2graph(
    graph_capturing_sheet: dict[str, pd.DataFrame], transformation_rule: TransformationRules, separator: str = ","
):
    """Converts a graph capturing sheet to an RDF graph

    Parameters
    ----------
    graph_capturing_sheet : dict[str, pd.DataFrame]
        Graph capturing sheet
    transformation_rule : TransformationRules
        Transformation rules
    separator : str, optional
        Multi value separator, by default ","
    """
    # Validation that everything is in order before proceeding
    validate_if_graph_capturing_sheet_empty(graph_capturing_sheet)
    validate_rules_graph_pair(graph_capturing_sheet, transformation_rule)

    # get class property pairs
    class_property_pairs = transformation_rule.get_class_property_pairs()

    # Now create empty graph
    graph = Graph()

    # Add namespaces
    for prefix, namespace in transformation_rule.prefixes.items():
        graph.bind(prefix, namespace)
    graph.bind(transformation_rule.metadata.prefix, transformation_rule.metadata.namespace)

    # Add triples from graph capturing sheet
    # iterate over sheets
    for sheet_name, df in graph_capturing_sheet.items():
        # iterate over sheet rows
        for _, row in df.iterrows():
            if row.identifier is None:
                logging.warning(f"Missing identifier in sheet {sheet_name} at row {row.name}! Skipping...")
                warnings.warn(
                    f"Missing identifier in sheet {sheet_name} at row {row.name}! Skipping...",
                    stacklevel=2,
                )
                continue

            # iterate over sheet rows properties
            for property_, value in row.to_dict().items():
                if property_ == "identifier":
                    graph.add(
                        (
                            transformation_rule.metadata.namespace[row.identifier],
                            RDF.type,
                            transformation_rule.metadata.namespace[sheet_name],
                        )
                    )

                elif class_property_pairs[sheet_name][property_].property_type == "ObjectProperty" and value:
                    for v in value.split(separator):
                        graph.add(
                            (
                                transformation_rule.metadata.namespace[row.identifier],
                                transformation_rule.metadata.namespace[property_],
                                transformation_rule.metadata.namespace[v.strip()],
                            )
                        )
                elif value:
                    graph.add(
                        (
                            transformation_rule.metadata.namespace[row.identifier],
                            transformation_rule.metadata.namespace[property_],
                            Literal(value),
                        )
                    )

    return graph


def validate_if_graph_capturing_sheet_empty(graph_capturing_sheet: dict[str, pd.DataFrame]):
    """Validate if the graph capturing sheet is empty

    Parameters
    ----------
    graph_capturing_sheet : dict[str, pd.DataFrame]
        Graph capturing sheet
    """
    if all(df.empty for df in graph_capturing_sheet.values()):
        logging.error("Graph capturing sheet is empty! Aborting!")
        raise ValueError("Graph capturing sheet is empty! Aborting!")


def validate_rules_graph_pair(graph_capturing_sheet: dict[str, pd.DataFrame], transformation_rule: TransformationRules):
    """Validate if the graph capturing sheet is based on the transformation rules

    Parameters
    ----------
    graph_capturing_sheet : dict[str, pd.DataFrame]
        Graph capturing sheet
    transformation_rule : TransformationRules
        Transformation rules
    """
    intersection = set(graph_capturing_sheet.keys()).intersection(set(transformation_rule.get_defined_classes()))

    if not intersection:
        logging.error("Graph capturing sheet is not based on transformation rules! Aborting!")
        raise ValueError("Graph capturing sheet is not based on transformation rules! Aborting!")

    elif len(intersection) == len(graph_capturing_sheet.keys()):
        logging.info("All classes in the graph capturing sheet are defined in the transformation rules!")

    elif len(intersection) < len(graph_capturing_sheet.keys()):
        logging.warning(
            "Graph capturing sheet contains classes that are not defined in the transformation rules! Proceeding..."
        )
        warnings.warn(
            "Graph capturing sheet contains classes that are not defined in the transformation rules! Proceeding...",
            stacklevel=2,
        )

    elif len(intersection) < len(transformation_rule.get_defined_classes()):
        logging.warning(
            "Transformation rules contain classes that are not present in the graph capturing sheet! Proceeding..."
        )
        warnings.warn(
            "Transformation rules contain classes that are not present in the graph capturing sheet! Proceeding...",
            stacklevel=2,
        )
