import logging
import warnings
from typing import Any, Hashable
from warnings import warn

import pandas as pd
from pydantic import field_validator
from pydantic_core import ErrorDetails, ValidationError
from rdflib import Namespace

from cognite.neat.core.configuration import PREFIXES
from cognite.neat.core.rules import _exceptions
from cognite.neat.core.rules.models import Class, Metadata, Property, RuleModel, TransformationRules


def from_tables(
    raw_dfs: dict[str, pd.DataFrame], return_report: bool = False
) -> tuple[TransformationRules | None, list[ErrorDetails] | None, list | None] | TransformationRules:
    # the only way to suppress warnings from pylense
    validation_warnings: list
    try:
        with warnings.catch_warnings(record=True) as validation_warnings:
            raw_tables = RawTables.from_raw_dataframes(raw_dfs)
            rules_dict: dict[str, Any] = {
                "metadata": _parse_metadata(raw_tables.Metadata),
                "classes": _parse_classes(raw_tables.Classes),
                "properties": _parse_properties(raw_tables.Properties),
                "prefixes": PREFIXES if raw_tables.Prefixes.empty else _parse_prefixes(raw_tables.Prefixes),
            }

            rules_dict["instances"] = (
                None
                if raw_tables.Instances.empty
                else _parse_instances(raw_tables.Instances, rules_dict["metadata"], rules_dict["prefixes"])
            )
            rules = TransformationRules(**rules_dict)
        return (rules, None, _exceptions.wrangle_warnings(validation_warnings)) if return_report else rules

    except _exceptions.Error0 as e:
        validation_errors = [e.to_error_dict()]
        if return_report:
            return None, validation_errors, _exceptions.wrangle_warnings(validation_warnings)
        else:
            raise e
    except ValidationError as e:
        validation_errors = e.errors()
        if return_report:
            return None, validation_errors, _exceptions.wrangle_warnings(validation_warnings)
        else:
            raise e


def _parse_metadata(meta_df: pd.DataFrame) -> dict[str, Any]:
    metadata_dict = dict(zip(meta_df[0], meta_df[1]))
    metadata_dict["source"] = meta_df.source if "source" in dir(meta_df) else None
    if "namespace" in metadata_dict:
        metadata_dict["namespace"] = Namespace(metadata_dict["namespace"])
    return metadata_dict


def _parse_classes(classes_df: pd.DataFrame) -> dict[Any | None, dict[Hashable, Any]]:
    return {class_.get("Class"): class_ for class_ in classes_df.to_dict(orient="records")}


def _parse_properties(properties_df: pd.DataFrame) -> dict[str, dict[Hashable, Any]]:
    return {f"row {i+3}": property_ for i, property_ in enumerate(properties_df.to_dict(orient="records"))}


def _parse_prefixes(prefix_df: pd.DataFrame) -> dict[str, Namespace]:
    return {row["Prefix"]: Namespace(row["URI"]) for i, row in prefix_df.iterrows()}


def _parse_instances(
    instances_df: pd.DataFrame, metadata: dict[str, Any], prefixes: dict[str, Namespace]
) -> list[tuple] | None:
    if "prefix" not in metadata or "namespace" not in metadata:
        logging.warning(_exceptions.Warning500().message)
        warn(_exceptions.Warning500().message)
        return None

    prefixes[metadata["prefix"]] = metadata["namespace"]

    instances = []
    for _, row in instances_df.iterrows():
        row_as_dict = row.to_dict()
        row_as_dict["namespace"] = metadata["namespace"]
        row_as_dict["prefixes"] = prefixes
        instances.append(row_as_dict)
    return instances


class RawTables(RuleModel):
    Metadata: pd.DataFrame
    Properties: pd.DataFrame
    Classes: pd.DataFrame
    Prefixes: pd.DataFrame = pd.DataFrame()
    Instances: pd.DataFrame = pd.DataFrame()

    @classmethod
    def from_raw_dataframes(cls, raw_dfs: dict[str, pd.DataFrame]) -> "RawTables":
        expected_tables = cls.mandatory()

        # Validate raw tables
        if missing_tables := (expected_tables - set(raw_dfs)):
            raise _exceptions.Error0(missing_tables)

        tables_dict = {
            Tables.metadata: raw_dfs[Tables.metadata],
            Tables.classes: raw_dfs[Tables.classes],
            Tables.properties: raw_dfs[Tables.properties],
        }

        if Tables.prefixes in raw_dfs:
            tables_dict[Tables.prefixes] = raw_dfs[Tables.prefixes]
        if Tables.instances in raw_dfs:
            tables_dict[Tables.instances] = raw_dfs[Tables.instances]

        return cls(**tables_dict)

    @field_validator("Metadata")
    def has_metadata_mandatory_rows(cls, v):
        given_rows = set(v[0].values)
        mandatory_rows = Metadata.mandatory()
        mandatory_rows_alias = Metadata.mandatory(use_alias=True)

        if not (mandatory_rows.issubset(given_rows) or mandatory_rows_alias.issubset(given_rows)):
            missing_rows = mandatory_rows_alias.difference(given_rows)
            raise _exceptions.Error51(missing_rows).to_pydantic_custom_error()
        return v

    @field_validator("Classes")
    def has_classes_mandatory_columns(cls, v):
        given_columns = set(v.columns)
        mandatory_columns = Class.mandatory()
        mandatory_columns_alias = Class.mandatory(use_alias=True)

        if not (mandatory_columns.issubset(given_columns) or mandatory_columns_alias.issubset(given_columns)):
            missing_columns = mandatory_columns_alias.difference(given_columns)
            raise _exceptions.Error52(missing_columns).to_pydantic_custom_error()
        return v

    @field_validator("Properties")
    def has_properties_mandatory_columns(cls, v):
        given_columns = set(v.columns)
        mandatory_columns = Property.mandatory()
        mandatory_columns_alias = Property.mandatory(use_alias=True)

        if not (mandatory_columns.issubset(given_columns) or mandatory_columns_alias.issubset(given_columns)):
            missing_columns = mandatory_columns_alias.difference(given_columns)
            raise _exceptions.Error53(missing_columns).to_pydantic_custom_error()
        return v

    @field_validator("Prefixes")
    def has_prefixes_mandatory_columns(cls, v):
        given_columns = set(v.columns)
        mandatory_columns = {"Prefix", "URI"}

        if not mandatory_columns.issubset(given_columns):
            missing_columns = mandatory_columns.difference(given_columns)
            raise _exceptions.Error54(missing_columns).to_pydantic_custom_error()
        return v

    @field_validator("Instances")
    def has_instances_mandatory_columns(cls, v):
        given_columns = set(v.columns)
        mandatory_columns = {"Instance", "Property", "Value"}

        if not mandatory_columns.issubset(given_columns):
            missing_columns = mandatory_columns.difference(given_columns)
            raise _exceptions.Error55(missing_columns).to_pydantic_custom_error()
        return v


class Tables:
    prefixes = "Prefixes"
    properties = "Properties"
    classes = "Classes"
    metadata = "Metadata"
    instances = "Instances"
