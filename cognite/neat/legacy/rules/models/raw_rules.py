import logging
import warnings
from collections.abc import Hashable
from typing import Any, cast, no_type_check
from warnings import warn

import pandas as pd
from pydantic import field_validator
from pydantic_core import ErrorDetails, ValidationError
from rdflib import Namespace

from cognite.neat.constants import PREFIXES
from cognite.neat.exceptions import wrangle_warnings

# rules model and model components:
from cognite.neat.legacy.rules.models.rules import Class, Metadata, Property, RuleModel, Rules
from cognite.neat.legacy.rules.models.tables import Tables

# importers:
from cognite.neat.rules import exceptions
from cognite.neat.utils.utils import generate_exception_report

__all__ = ["RawRules"]


class RawRules(RuleModel):
    """
    RawRules represent invalidated form of Rules, which is a core concept in `neat`.
    RawRules are used as staging area for Rules, and are often used when importing rules
    from sources other than Excel rules, e.g. from a json schema or owl ontology. Often
    these sources are not validated, and are missing information to be able to create
    a valid Rules object.

    Args:
        Metadata: Data model metadata
        classes: Classes defined in the data model
        properties: Class properties defined in the data model with accompanying transformation rules
                    to transform data from source to target representation
        prefixes: Prefixes used in the data model. Defaults to PREFIXES
        instances: Instances defined in the data model. Defaults to None
    """

    Metadata: pd.DataFrame
    Classes: pd.DataFrame
    Properties: pd.DataFrame
    Prefixes: pd.DataFrame = pd.DataFrame()
    Instances: pd.DataFrame = pd.DataFrame()
    importer_type: str = "RawTablesImporter"

    @field_validator("Metadata")
    def has_metadata_mandatory_rows(cls, v: pd.DataFrame):
        given_rows = set(v.iloc[:, 0].values)
        mandatory_rows = Metadata.mandatory_fields()
        mandatory_rows_alias = Metadata.mandatory_fields(use_alias=True)

        if not (mandatory_rows.issubset(given_rows) or mandatory_rows_alias.issubset(given_rows)):
            missing_rows = mandatory_rows_alias.difference(given_rows)
            raise exceptions.MetadataSheetMissingMandatoryFields(missing_rows).to_pydantic_custom_error()
        return v

    @field_validator("Classes")
    def has_classes_mandatory_columns(cls, v):
        given_columns = set(v.columns)
        mandatory_columns = Class.mandatory_fields()
        mandatory_columns_alias = Class.mandatory_fields(use_alias=True)

        if not (mandatory_columns.issubset(given_columns) or mandatory_columns_alias.issubset(given_columns)):
            missing_columns = mandatory_columns_alias.difference(given_columns)
            raise exceptions.ClassesSheetMissingMandatoryColumns(missing_columns).to_pydantic_custom_error()
        return v

    @field_validator("Properties")
    def has_properties_mandatory_columns(cls, v):
        given_columns = set(v.columns)
        mandatory_columns = Property.mandatory_fields()
        mandatory_columns_alias = Property.mandatory_fields(use_alias=True)

        if not (mandatory_columns.issubset(given_columns) or mandatory_columns_alias.issubset(given_columns)):
            missing_columns = mandatory_columns_alias.difference(given_columns)
            raise exceptions.PropertiesSheetMissingMandatoryColumns(missing_columns).to_pydantic_custom_error()
        return v

    @field_validator("Prefixes")
    def has_prefixes_mandatory_columns(cls, v):
        given_columns = set(v.columns)
        mandatory_columns = {"Prefix", "URI"}

        if not mandatory_columns.issubset(given_columns):
            missing_columns = mandatory_columns.difference(given_columns)
            raise exceptions.PrefixesSheetMissingMandatoryColumns(missing_columns).to_pydantic_custom_error()
        return v

    @field_validator("Instances")
    def has_instances_mandatory_columns(cls, v):
        given_columns = set(v.columns)
        mandatory_columns = {"Instance", "Property", "Value"}

        if not mandatory_columns.issubset(given_columns):
            missing_columns = mandatory_columns.difference(given_columns)
            raise exceptions.InstancesSheetMissingMandatoryColumns(missing_columns).to_pydantic_custom_error()
        return v

    @staticmethod
    def _drop_non_string_columns(df: pd.DataFrame) -> pd.DataFrame:
        """Drop non-string columns as this can cause issue when loading rules

        Args:
            df: data frame

        Returns:
            dataframe with removed non string columns
        """
        columns = [column for column in df.columns[df.columns.notna()] if isinstance(column, str)]

        return df[columns]

    # mypy complains "RawRules" has incompatible type "**dict[str, DataFrame]"; expected "set[str]" , which is wrong!
    @no_type_check
    @classmethod
    def from_tables(cls, tables: dict[str, pd.DataFrame], importer_type: str = "RawTablesImporter") -> "RawRules":
        """Create RawRules from raw tables.

        Args:
            tables: Tables to be converted to RawRules

        Returns:
            Instance of RawRules
        """

        expected_tables = cls.mandatory_fields()

        # Validate raw tables
        if missing_tables := (expected_tables - set(tables)):
            raise exceptions.SourceObjectDoesNotProduceMandatorySheets(missing_tables)

        tables_dict: dict[str, pd.DataFrame] = {
            Tables.metadata: tables[Tables.metadata],
            Tables.classes: cls._drop_non_string_columns(tables[Tables.classes]),
            Tables.properties: cls._drop_non_string_columns(tables[Tables.properties]),
        }

        if Tables.prefixes in tables:
            tables_dict[Tables.prefixes] = cls._drop_non_string_columns(tables[Tables.prefixes])
        if Tables.instances in tables:
            tables_dict[Tables.instances] = cls._drop_non_string_columns(tables[Tables.instances])

        return cls(
            **tables_dict,
            importer_type=importer_type,
        )

    # mypy unsatisfied with overload , tried all combination and gave up
    @no_type_check
    def to_rules(
        self,
        return_report: bool = False,
        skip_validation: bool = False,
        validators_to_skip: set[str] | None = None,
    ) -> tuple[Rules | None, list[ErrorDetails] | None, list | None] | Rules:
        """Validates RawRules instances and returns Rules instance.

        Args:
            return_report: To return validation report. Defaults to False.
            skip_validation: Bypasses Rules validation. Defaults to False.
            validators_to_skip: List of validators to skip. Defaults to None.

        Returns:
            Instance of `Rules`, which can be validated or not validated based on
            `skip_validation` flag, and optional list of errors and warnings if
            `return_report` is set to True.

        !!! Note
            `skip_validation` flag should be only used for purpose when `Rules` object
            is exported to an Excel file. Do not use this flag for any other purpose!
        """

        rules_dict = _raw_tables_to_rules_dict(self, validators_to_skip)
        if skip_validation:
            return _to_invalidated_rules(rules_dict)
        else:
            return _to_validated_rules(rules_dict, return_report)

    def validate_rules(self) -> str | None:
        _, errors, warnings_ = self.to_rules(return_report=True, skip_validation=False)

        report = ""
        if errors:
            warnings.warn(
                exceptions.RulesHasErrors(importer_type=self.importer_type).message,
                category=exceptions.RulesHasErrors,
                stacklevel=2,
            )
            report = generate_exception_report(cast(list[ErrorDetails], errors), "Errors")

        if warnings_:
            warnings.warn(
                exceptions.RulesHasWarnings(importer_type=self.importer_type).message,
                category=exceptions.RulesHasWarnings,
                stacklevel=2,
            )
            report += generate_exception_report(cast(list[dict], warnings_), "Warnings")

        return report if report else None


def _to_validated_rules(
    rules_dict: dict, return_report: bool = False
) -> tuple[Rules | None, list[ErrorDetails] | None, list[dict] | None] | Rules:
    validation_warnings = []
    try:
        with warnings.catch_warnings(record=True) as validation_warnings:
            rules = Rules(**rules_dict)
        return (rules, None, wrangle_warnings(validation_warnings)) if return_report else rules

    except ValidationError as e:
        validation_errors = e.errors()
        if return_report:
            return None, validation_errors, wrangle_warnings(validation_warnings)
        else:
            raise e


def _to_invalidated_rules(rules_dict: dict) -> Rules:
    args = {
        "metadata": Metadata.model_construct(**rules_dict["metadata"]),
        "classes": {
            class_: Class.model_construct(**definition) for class_, definition in rules_dict["classes"].items()
        },
        "properties": {
            property_: Property.model_construct(**definition)
            for property_, definition in rules_dict["properties"].items()
        },
        "prefixes": rules_dict["prefixes"],
    }

    return cast(Rules, Rules.model_construct(**args))


def _raw_tables_to_rules_dict(raw_tables: RawRules, validators_to_skip: set | None = None) -> dict[str, Any]:
    """Converts raw tables to a dictionary of rules."""
    rules_dict: dict[str, Any] = {
        "metadata": _metadata_table2dict(raw_tables.Metadata),
        "classes": _classes_table2dict(raw_tables.Classes),
        "properties": _properties_table2dict(raw_tables.Properties),
        "prefixes": PREFIXES if raw_tables.Prefixes.empty else _prefixes_table2dict(raw_tables.Prefixes),
    }

    rules_dict["instances"] = (
        None
        if raw_tables.Instances.empty
        else _instances_table2dict(raw_tables.Instances, rules_dict["metadata"], rules_dict["prefixes"])
    )

    if validators_to_skip:
        rules_dict["validators_to_skip"] = validators_to_skip
        rules_dict["metadata"]["validators_to_skip"] = validators_to_skip
        for class_ in rules_dict["classes"].keys():
            rules_dict["classes"][class_]["validators_to_skip"] = validators_to_skip
        for property_ in rules_dict["properties"].keys():
            rules_dict["properties"][property_]["validators_to_skip"] = validators_to_skip

    return rules_dict


def _metadata_table2dict(meta_df: pd.DataFrame) -> dict[str, Any]:
    assert len(meta_df.columns) == 2
    col1, col2 = meta_df.columns
    metadata_dict = dict(zip(meta_df[col1], meta_df[col2], strict=True))
    metadata_dict["source"] = meta_df.source if "source" in dir(meta_df) else None
    if "namespace" in metadata_dict:
        metadata_dict["namespace"] = Namespace(metadata_dict["namespace"])
    return metadata_dict


def _classes_table2dict(classes_df: pd.DataFrame) -> dict[Any | None, dict[Hashable, Any]]:
    return {class_.get("Class"): class_ for class_ in classes_df.to_dict(orient="records")}


def _properties_table2dict(properties_df: pd.DataFrame) -> dict[str, dict[Hashable, Any]]:
    return {f"row {i+3}": property_ for i, property_ in enumerate(properties_df.to_dict(orient="records"))}


def _prefixes_table2dict(prefix_df: pd.DataFrame) -> dict[str, Namespace]:
    return {row["Prefix"]: Namespace(row["URI"]) for i, row in prefix_df.iterrows()}


def _instances_table2dict(
    instances_df: pd.DataFrame, metadata: dict[str, Any], prefixes: dict[str, Namespace]
) -> list[dict] | None:
    if ("prefix" not in metadata and "namespace" not in metadata) or "namespace" not in metadata:
        logging.warning(exceptions.MissingDataModelPrefixOrNamespace().message)
        warn(exceptions.MissingDataModelPrefixOrNamespace().message, stacklevel=2)
        return None

    prefix = metadata["prefix"] if "prefix" in metadata else metadata["space"]
    prefixes[prefix] = metadata["namespace"]

    instances = []
    for _, row in instances_df.iterrows():
        row_as_dict = row.to_dict()
        row_as_dict["namespace"] = metadata["namespace"]
        row_as_dict["prefixes"] = prefixes
        instances.append(row_as_dict)
    return instances
