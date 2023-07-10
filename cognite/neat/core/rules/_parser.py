import logging

import pandas as pd
from rdflib import Namespace

from .models import URL, Instance, Metadata, Prefixes, TransformationRules


def from_tables(raw_dfs: dict[str, pd.DataFrame], allow_validation_errors: bool = False) -> TransformationRules:
    expected_tables = Tables.as_set()
    if missing_tables := (expected_tables - set(raw_dfs)):
        raise ValueError(f"Missing the following tables {', '.join(missing_tables)}")

    metadata = _parse_metadata(raw_dfs[Tables.metadata])
    prefixes = _parse_prefix(raw_dfs[Tables.prefixes])

    instances = _parse_instances(raw_dfs, metadata, prefixes) if Tables.instances in raw_dfs else None

    if not allow_validation_errors:
        return TransformationRules(
            prefixes=prefixes,
            metadata=metadata,
            classes={class_.get("Class"): class_ for class_ in raw_dfs[Tables.classes].to_dict(orient="records")},
            properties={
                f"row {i+3}": property_
                for i, property_ in enumerate(raw_dfs[Tables.properties].to_dict(orient="records"))
            },
            instances=instances,
        )
    else:
        raise NotImplementedError("Allowing validation errors is not yet implemented!")


def _parse_instances(raw_dfs: dict[str, pd.DataFrame], metadata: Metadata, prefixes: Prefixes) -> list[tuple]:
    prefixes[metadata.prefix] = metadata.namespace

    instances = []
    for row_no, row in raw_dfs[Tables.instances].iterrows():
        try:
            triple = Instance(**row.to_dict(), namespace=metadata.namespace, prefixes=prefixes)
        except Exception:
            msg = f"Skipping row <{row_no + 3}> in Instance sheet\nReason: prefix in Property or Value column not defined!\n"
            print(msg)
            logging.info(msg)
        else:
            instances += [(triple.instance, triple.property_, triple.value)]

    return instances


def _parse_metadata(meta_df: pd.DataFrame) -> Metadata:
    return Metadata(
        **dict(zip(meta_df[0], meta_df[1])),
        source=meta_df.source if "source" in dir(meta_df) else None,
    )


def _parse_prefix(prefix_df: pd.DataFrame) -> dict[str, Namespace]:
    prefixes = {}
    for i, row in prefix_df.iterrows():
        try:
            url = URL(url=row["URI"]).url
            prefixes[row["Prefix"]] = Namespace(url)
        except ValueError as e:
            msg = f"Prefix <{row['Prefix']}> has invalid URL: <{row['URI']}> fix this in Prefixes sheet at the row {i + 2} in the rule file!"
            logging.error(msg)
            raise ValueError(msg) from e

    return prefixes


class Tables:
    prefixes = "Prefixes"
    properties = "Properties"
    classes = "Classes"
    metadata = "Metadata"
    instances = "Instances"

    @classmethod
    def as_set(cls) -> set[str]:
        return {value for attr, value in cls.__dict__.items() if not attr.startswith("_") and attr != "as_set"}
