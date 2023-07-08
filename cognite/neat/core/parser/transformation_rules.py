import logging

import pandas as pd

from cognite.neat.core.configuration import Tables
from cognite.neat.core.rules import Instance, Metadata, Prefixes, TransformationRules


def parse_transformation_rules(
    raw_dfs: dict[str, pd.DataFrame], allow_validation_errors: bool = False
) -> TransformationRules:
    metadata = Metadata.create_from_dataframe(raw_dfs)
    prefixes = Prefixes.create_from_dataframe(raw_dfs[Tables.prefixes])
    instances = parse_instances(raw_dfs, metadata, prefixes) if Tables.instances in raw_dfs else None

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


def parse_instances(raw_dfs: dict[str, pd.DataFrame], metadata: Metadata, prefixes: Prefixes) -> list[tuple]:
    expected_tables = Tables.as_set()
    if missing_tables := (expected_tables - set(raw_dfs)):
        raise ValueError(f"Missing the following tables {', '.join(missing_tables)}")

    prefixes[metadata.prefix] = metadata.namespace

    instances = []
    for row_no, row in raw_dfs[Tables.instances].iterrows():
        try:
            triple = Instance(**row.to_dict(), namespace=metadata.namespace, prefixes=prefixes)
            instances += [(triple.instance, triple.property_, triple.value)]
        except Exception:
            msg = f"Skipping row <{row_no + 3}> in Instance sheet\nReason: prefix in Property or Value column not defined!\n"
            print(msg)
            logging.info(msg)

    return instances
