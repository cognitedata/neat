import logging
from typing import Any
from warnings import warn

import pandas as pd
from rdflib import Namespace

from cognite.neat.core.configuration import PREFIXES

from . import _exceptions
from .models import TransformationRules


def from_tables(raw_dfs: dict[str, pd.DataFrame]) -> TransformationRules:
    transformation_rules: dict[str, Any] = {}

    expected_tables = Tables.mandatory()
    if missing_tables := (expected_tables - set(raw_dfs)):
        raise ValueError(f"Missing the following tables {', '.join(missing_tables)}")

    # cannot fail for any circumstances
    transformation_rules["metadata"] = _parse_metadata(raw_dfs[Tables.metadata])
    transformation_rules["classes"] = _parse_classes(raw_dfs[Tables.classes])
    transformation_rules["properties"] = _parse_properties(raw_dfs[Tables.properties])
    transformation_rules["prefixes"] = (
        _parse_prefixes(raw_dfs[Tables.prefixes]) if Tables.prefixes in raw_dfs else PREFIXES
    )

    if (
        "prefix" in transformation_rules["metadata"]
        and "namespace" in transformation_rules["metadata"]
        and Tables.instances in raw_dfs
    ):
        namespace = Namespace(transformation_rules["metadata"]["namespace"])
        prefix = transformation_rules["metadata"]["prefix"]
        transformation_rules["prefixes"][prefix] = namespace
        transformation_rules["instances"] = None
        # transformation_rules["instances"] = _parse_instances(
        #     raw_dfs[Tables.instances], namespace, transformation_rules["prefixes"]
        # )
    elif Tables.instances in raw_dfs:
        logging.warning(_exceptions.Warning500().message)
        warn(_exceptions.Warning500().message)
        transformation_rules["instances"] = None
    else:
        transformation_rules["instances"] = None

    # this is where it can fail
    return TransformationRules(**transformation_rules)


def _parse_metadata(meta_df: pd.DataFrame) -> dict[str, Any]:
    metadata_dict = dict(zip(meta_df[0], meta_df[1]))
    metadata_dict["source"] = meta_df.source if "source" in dir(meta_df) else None
    return metadata_dict


def _parse_classes(classes_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {class_.get("Class"): class_ for class_ in classes_df.to_dict(orient="records")}


def _parse_properties(properties_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {f"row {i+3}": property_ for i, property_ in enumerate(properties_df.to_dict(orient="records"))}


def _parse_prefixes(prefix_df: pd.DataFrame) -> dict[str, Namespace]:
    return {row["Prefix"]: Namespace(row["URI"]) for i, row in prefix_df.iterrows()}


# def _parse_instances(instances_df: pd.DataFrame, namespace: Namespace, prefixes: dict[str, Namespace]) -> list[tuple]:
#     instances = []
#     for row_no, row in instances_df.iterrows():
#         instances += []
#         try:
#             triple = Instance(**row.to_dict(), namespace=metadata.namespace, prefixes=prefixes)
#         except Exception:
#             msg = f"Skipping row <{row_no + 3}> in Instance sheet\nReason: prefix in Property or Value column not defined!\n"
#             print(msg)
#             logging.info(msg)
#         else:
#             instances += [(triple.instance, triple.property_, triple.value)]

#     return instances


class Tables:
    prefixes = "Prefixes"
    properties = "Properties"
    classes = "Classes"
    metadata = "Metadata"
    instances = "Instances"

    @classmethod
    def as_set(cls) -> set[str]:
        return {value for attr, value in cls.__dict__.items() if not attr.startswith("_") and attr != "as_set"}

    @classmethod
    def mandatory(cls) -> set[str]:
        return {
            "Metadata",
            "Classes",
            "Properties",
        }
