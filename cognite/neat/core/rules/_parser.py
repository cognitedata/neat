import logging
from typing import Any
from warnings import warn

import pandas as pd
from pydantic import BaseModel
from rdflib import Namespace

from cognite.neat.core.configuration import PREFIXES

from . import _exceptions
from .models import Class, Instance, Metadata, Property, TransformationRules


def from_tables(raw_dfs: dict[str, pd.DataFrame]) -> TransformationRules:
    transformation_rules: dict[str, Any] = {}

    expected_tables = Tables.mandatory()

    # Validate raw tables
    # Missing mandatory sheets/tables
    if missing_tables := (expected_tables - set(raw_dfs)):
        raise ValueError(f"Missing the following tables {', '.join(missing_tables)}")
    # Missing mandatory columns/raws per sheets/tables
    _validate_raw_tables(raw_dfs)

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
        namespace = transformation_rules["metadata"]["namespace"]
        prefix = transformation_rules["metadata"]["prefix"]
        transformation_rules["prefixes"][prefix] = namespace
        transformation_rules["instances"] = _parse_instances(
            raw_dfs[Tables.instances], namespace, transformation_rules["prefixes"]
        )
    elif Tables.instances in raw_dfs:
        logging.warning(_exceptions.Warning500().message)
        warn(_exceptions.Warning500().message)
        transformation_rules["instances"] = None
    else:
        transformation_rules["instances"] = None

    # Fail content validation
    return TransformationRules(**transformation_rules)


def _parse_metadata(meta_df: pd.DataFrame) -> dict[str, Any]:
    metadata_dict = dict(zip(meta_df[0], meta_df[1]))
    metadata_dict["source"] = meta_df.source if "source" in dir(meta_df) else None
    if "namespace" in metadata_dict:
        metadata_dict["namespace"] = Namespace(metadata_dict["namespace"])
    return metadata_dict


def _parse_classes(classes_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {class_.get("Class"): class_ for class_ in classes_df.to_dict(orient="records")}


def _parse_properties(properties_df: pd.DataFrame) -> dict[str, dict[str, Any]]:
    return {f"row {i+3}": property_ for i, property_ in enumerate(properties_df.to_dict(orient="records"))}


def _parse_prefixes(prefix_df: pd.DataFrame) -> dict[str, Namespace]:
    return {row["Prefix"]: Namespace(row["URI"]) for i, row in prefix_df.iterrows()}


def _parse_instances(instances_df: pd.DataFrame, namespace: Namespace, prefixes: dict[str, Namespace]) -> list[tuple]:
    instances = []
    for _, row in instances_df.iterrows():
        row_as_dict = row.to_dict()
        row_as_dict["namespace"] = namespace
        row_as_dict["prefixes"] = prefixes
        instances.append(row_as_dict)
    return instances


def _validate_raw_tables(raw_dfs: dict[str, pd.DataFrame]):
    """Validate that the raw tables contain the required fields (i.e. columns and rows)

    Parameters
    ----------
    raw_dfs : dict[str, pd.DataFrame]
        Raw tables from excel file provided as dataframes
    """
    # TODO: Figure out how to use ExceptionGroup here

    exceptions = []

    if not (
        _get_required_fields(Metadata, use_alias=False).issubset(set(raw_dfs[Tables.metadata][0].values))
        or _get_required_fields(Metadata, use_alias=True).issubset(set(raw_dfs[Tables.metadata][0].values))
    ):
        missing_fields = _get_required_fields(Metadata, use_alias=False).difference(
            set(raw_dfs[Tables.metadata][0].values)
        )
        exceptions.append(_exceptions.Error51(missing_fields))

    if not (
        _get_required_fields(Class, use_alias=False).issubset(set(raw_dfs[Tables.classes].columns))
        or _get_required_fields(Class, use_alias=True).issubset(set(raw_dfs[Tables.classes].columns))
    ):
        missing_fields = _get_required_fields(Class, use_alias=True).difference(set(raw_dfs[Tables.classes].columns))
        exceptions.append(_exceptions.Error52(missing_fields))

    if not (
        _get_required_fields(Property, use_alias=False).issubset(set(raw_dfs[Tables.properties].columns))
        or _get_required_fields(Property, use_alias=True).issubset(set(raw_dfs[Tables.properties].columns))
    ):
        missing_fields = _get_required_fields(Property, use_alias=True).difference(
            set(raw_dfs[Tables.properties].columns)
        )
        exceptions.append(_exceptions.Error53(missing_fields))

    # TODO: move hardcoded column names to constants
    if (Tables.prefixes in raw_dfs) and not ({"Prefix", "URI"}.issubset(set(raw_dfs[Tables.prefixes].columns))):
        missing_fields = {"Prefix", "URI"}.difference(set(raw_dfs[Tables.prefixes].columns))
        exceptions.append(_exceptions.Error54(missing_fields))

    # TODO: move hardcoded column names to constants
    if (Tables.instances in raw_dfs) and not (
        _get_required_fields(Instance, use_alias=False)
        .difference({"namespace", "prefixes"})
        .issubset(set(raw_dfs[Tables.instances].columns))
        or _get_required_fields(Instance, use_alias=True)
        .difference({"namespace", "prefixes"})
        .issubset(set(raw_dfs[Tables.instances].columns))
    ):
        missing_fields = _get_required_fields(Instance, use_alias=True).difference(
            set(raw_dfs[Tables.instances].columns)
        )
        exceptions.append(_exceptions.Error55(missing_fields))

    if exceptions:
        raise _exceptions.Error56("\n".join([e.message for e in exceptions]))


def _get_required_fields(model: type[BaseModel], use_alias: bool = False) -> set[str]:
    """Get required fields from a pydantic model.

    Parameters
    ----------
    model : type[BaseModel]
        Pydantic data model
    use_alias : bool, optional
        Whether to return field alias name, by default False

    Returns
    -------
    list[str]
        List of required fields
    """
    required_fields = set()
    for name, field in model.model_fields.items():
        if not field.is_required():
            continue

        alias = getattr(field, "alias", None)
        if use_alias and alias:
            required_fields.add(alias)
        else:
            required_fields.add(name)
    return required_fields


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
