import logging
import warnings

import pandas as pd
from rdflib import RDF, XSD, Literal, Namespace

from cognite.neat.core.data_classes.transformation_rules import TransformationRules


def sheet2triples(
    graph_capturing_sheet: dict[str, pd.DataFrame],
    transformation_rule: TransformationRules,
    separator: str = ",",
    namespace: str = None,
) -> list[tuple]:
    """Converts a graph capturing sheet to rdf triples

    Parameters
    ----------
    graph_capturing_sheet : dict[str, pd.DataFrame]
        Graph capturing sheet
    transformation_rule : TransformationRules
        Transformation rules
    separator : str, optional
        Multi value separator at cell level, by default ","
    namespace : str, optional
        In case of a custom namespace, by default None meaning the namespace is taken from the transformation rules
    """
    # Validation that everything is in order before proceeding
    validate_if_graph_capturing_sheet_empty(graph_capturing_sheet)
    validate_rules_graph_pair(graph_capturing_sheet, transformation_rule)

    # get class property pairs
    class_property_pairs = transformation_rule.get_class_property_pairs()

    # namespace selection
    if namespace is None:
        instance_namespace = transformation_rule.metadata.namespace
    else:
        instance_namespace = Namespace(namespace)

    model_namespace = Namespace(transformation_rule.metadata.namespace)

    # Now create empty graph
    triples = []

    # Add triples from the capturing sheet to the graph by iterating over the capturing sheet
    # iterate over sheets
    for sheet_name, df in graph_capturing_sheet.items():
        # iterate over sheet rows
        for _, row in df.iterrows():
            if row.identifier is None:
                msg = f"Missing identifier in sheet {sheet_name} at row {row.name}! Skipping..."
                logging.warning(msg)
                warnings.warn(
                    msg,
                    stacklevel=2,
                )
                continue

            # iterate over sheet rows properties
            for property_, value in row.to_dict().items():
                # Setting RDF type of the instance
                if property_ == "identifier":
                    triples.append(
                        (
                            instance_namespace[row.identifier],
                            RDF.type,
                            model_namespace[sheet_name],
                        )
                    )

                # Adding object properties
                elif class_property_pairs[sheet_name][property_].property_type == "ObjectProperty" and value:
                    triples.extend(
                        (
                            instance_namespace[row.identifier],
                            model_namespace[property_],
                            instance_namespace[v.strip()],
                        )
                        for v in value.split(separator)
                    )

                # Adding data properties
                # TODO: Add support for datatype
                elif value:
                    triples.append(
                        (
                            instance_namespace[row.identifier],
                            model_namespace[property_],
                            Literal(
                                value, datatype=XSD[class_property_pairs[sheet_name][property_].expected_value_type]
                            ),
                        )
                    )
    return triples


def validate_if_graph_capturing_sheet_empty(graph_capturing_sheet: dict[str, pd.DataFrame]):
    """Validate if the graph capturing sheet is empty

    Parameters
    ----------
    graph_capturing_sheet : dict[str, pd.DataFrame]
        Graph capturing sheet
    """
    if all(df.empty for df in graph_capturing_sheet.values()):
        msg = "Graph capturing sheet is empty! Aborting!"
        logging.error(msg)
        raise ValueError(msg)


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
        msg = "Graph capturing sheet is not based on transformation rules! Aborting!"
        logging.error(msg)
        raise ValueError(msg)

    elif len(intersection) == len(graph_capturing_sheet.keys()):
        logging.info("All classes in the graph capturing sheet are defined in the transformation rules!")

    elif len(intersection) < len(graph_capturing_sheet.keys()):
        msg = "Graph capturing sheet contains classes that are not defined in the transformation rules! Proceeding..."
        logging.warning(msg)
        warnings.warn(
            msg,
            stacklevel=2,
        )

    elif len(intersection) < len(transformation_rule.get_defined_classes()):
        msg = "Transformation rules contain classes that are not present in the graph capturing sheet! Proceeding..."
        logging.warning(msg)
        warnings.warn(
            msg,
            stacklevel=2,
        )
