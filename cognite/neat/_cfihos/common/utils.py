import json
import pathlib
import re

import pandas as pd
from cognite.client.data_classes import data_modeling

from cognite.neat._cfihos.common.constants import MODEL_VERSION_LENGTH
from cognite.neat._cfihos.common.generic_classes import (
    DataSource,
    EntityStructure,
    PropertyStructure,
    ScopeConfig,
)
from cognite.neat._cfihos.common.log import log_init
from cognite.neat._cfihos.processing.cfihos import constants

logging = log_init(f"{__name__}", "i")


def read_scope(fpath: str, id_col: str) -> list[str]:
    if not fpath.endswith(".csv"):
        raise ValueError(f"Provided scope file {fpath} must be '.csv'")

    df = pd.read_csv(fpath)
    if id_col not in df.columns:
        raise KeyError(f"Given id column '{id_col}' is not present in scope file")
    scope = df[id_col].values
    if len(scope) != len(set(scope)):
        duplicate_ids = set([x for x in scope if list(scope).count(x) > 1])
        raise ValueError(f"Provided scope file with id column '{id_col}' contains duplicates: {duplicate_ids}")
    return scope


def read_input_sheet(
    fpath: str,
    source: DataSource = DataSource.default(),
    **kwargs,
) -> pd.DataFrame:
    """Read input sheet from a given data source `source`.

    Args:
        fpath (str): file path to the input sheet.
        source (DataSource, optional): source where input sheet resides. Defaults to DataSource.default() ("csv").

    Raises:
        ValueError: if `source` is not a valid DataSource. Could also consider this as a NotImplementedError.

    Returns:
        pd.DataFrame: pandas dataframe of the input sheet.
    """

    match source:
        case DataSource.CSV.value:
            return pd.read_csv(fpath, **kwargs)
        case DataSource.GITHUB.value:
            return pd.read_csv(fpath, **kwargs)  # TODO: add the original github integration code
        case _:
            raise ValueError(f"Unknown data source {source}")


def create_folder_structure_if_missing(path: str):
    pathlib.Path(path).mkdir(parents=True, exist_ok=True)


def to_pascal_case(s: str) -> str:
    s = re.sub(r"(_|-|,|\)|\(|/)+", " ", s).title().replace(" ", "")
    return "".join([s[0].upper(), s[1:]])


def to_camel_case(s: str) -> str:
    s = re.sub(r"(_|-|,|\)|\(|/)+", " ", s).title().replace(" ", "")
    return "".join([s[0].lower(), s[1:]])


def is_camel_case(s: str) -> bool:
    if not s[0].islower():
        return False
    s = s[0].upper() + s[1:]
    return s != s.lower() and s != s.upper()


def is_pascal_case(s: str) -> bool:
    return s[0].isupper() and is_camel_case(s=s[0].lower() + s[1:])


def generate_dms_friendly_name(name: str, max_length: int) -> str:
    name = to_pascal_case(name)
    if len(name) < max_length:
        return name
    # TODO - hacky solution
    offset_value = 10
    new_name = name[: max_length - offset_value] + "".join(
        [c for c in name[max_length - offset_value :] if c.isupper()]
    )
    if len(new_name) > max_length + MODEL_VERSION_LENGTH:
        raise ValueError(f"entity: New-name: {new_name} old name {name}")
    # print(f"[WARNING] - dms name: {name} was shorten to {new_name}")
    return new_name


def generate_dms_friendly_property_name(name: str, max_length: int):
    name = to_camel_case(name)
    if len(name) < max_length:
        return name
    # TODO - hacky solution
    offset_value = 10
    new_name = name[: max_length - offset_value] + "".join(
        [c for c in name[max_length - offset_value :] if c.isupper()]
    )

    if len(new_name) > max_length + MODEL_VERSION_LENGTH:
        raise ValueError(f"prop: New-name: {new_name} old name {name}")
    return new_name


def dfs(
    visited: set,
    entity_id: str,
    full_model: dict,
    map_dms_id_to_model_id: dict,
):
    if entity_id not in visited:
        visited.add(entity_id)
        entity_data = full_model[entity_id]
        extends = entity_data.get(EntityStructure.INHERITS_FROM_ID, [])

        if entity_data[EntityStructure.PROPERTIES]:
            properties_to_extend = set()
            for property in entity_data[EntityStructure.PROPERTIES]:
                if property[PropertyStructure.PROPERTY_TYPE] == "ENTITY_RELATION":
                    prop_target_type = map_dms_id_to_model_id.get(property[PropertyStructure.TARGET_TYPE], False)
                    if prop_target_type is False:
                        continue
                    if prop_target_type not in visited:
                        properties_to_extend.add(prop_target_type)
            for prop_to_extend in properties_to_extend:
                dfs(
                    visited,
                    prop_to_extend,
                    full_model,
                    map_dms_id_to_model_id,
                )
        if extends is None:
            return visited
        for parent in extends:
            parent_entity_id = map_dms_id_to_model_id[parent]
            dfs(
                visited,
                parent_entity_id,
                full_model,
                map_dms_id_to_model_id,
            )
    return visited


def collect_model_subset(
    full_model: dict,
    scope_config: str,
    scope: list[str],
    map_dms_id_to_model_id: dict,
):
    visited = set()  # Set to keep track of visited nodes of the graph
    # entities = {scope_model_id: full_model[scope_model_id] for scope_model_id in scope}
    entities = {
        cfihos_id: full_model[cfihos_id]
        for cfihos_id in full_model
        if (
            (scope_config == ScopeConfig.SCOPED and cfihos_id in scope)
            or (scope_config == ScopeConfig.TAGS and cfihos_id.startswith(constants.CFIHOS_TYPE_TAG_PREFIX))
            or (scope_config == ScopeConfig.EQUIPMENT and cfihos_id.startswith(constants.CFIHOS_TYPE_EQUIPMENT_PREFIX))
            or full_model[cfihos_id][EntityStructure.FIRSTCLASSCITIZEN]
        )
    }

    for entity_id in entities:
        visited = visited.union(
            dfs(
                visited,
                entity_id,
                full_model,
                map_dms_id_to_model_id,
            )
        )

    scoped_entities = {key: full_model[key] for key in visited}

    logging.info(f"Selected {len(visited)} objects from {len(full_model)}")
    return scoped_entities


def collect_property_subset(subset_model: dict, property_space: dict) -> dict:
    subset_model_properties = set()
    for entity_id, entity_data in subset_model.items():
        for prop in entity_data["properties"]:
            subset_model_properties.add(prop[PropertyStructure.ID])

    return {key: property_space[key] for key in subset_model_properties}


def save_json(data: list, fpath: str):
    # TODO: Deterministic serialization with predictable ordering of dict keys
    data_dump = [c.dump(camel_case=True) for c in data]
    # data_dump = [v.update({"properties": dict(sorted(v["properties"].items()))}) for v in data_dump]
    json.dump(data_dump, open(fpath, "w"), ensure_ascii=False, indent=4)


def get_entity_relation_target(Property_id, entity_id, entities) -> str | None:
    container_entity_properties = entities[entity_id]["properties"]
    for property in container_entity_properties:
        if (
            property[PropertyStructure.ID] == Property_id
            and property[PropertyStructure.TARGET_TYPE].replace("_", "-") in entities.keys()
            and entities[property[PropertyStructure.TARGET_TYPE].replace("_", "-")][EntityStructure.FIRSTCLASSCITIZEN]
        ):
            return property[PropertyStructure.TARGET_TYPE]

    return "#N/A" #"undefined"  # None


# TODO: add data types to the parameters in the below function
def get_relation_target_if_eligible(key, container_external_id, entities, property_type) -> str | None:
    """Determine the target only if the container meets the criteria."""
    if (
        container_external_id in entities
        and entities[container_external_id][EntityStructure.FIRSTCLASSCITIZEN]
        and container_external_id != "EntityTypeGroup"
        and (
            property_type == data_modeling.DirectRelation()
            or property_type == data_modeling.DirectRelation(is_list=True)
        )
    ):
        return get_entity_relation_target(key, container_external_id, entities)
    return "#N/A"  # None


def generate_neat_rules_sheet(
    output_file,
    df_metadata: pd.DataFrame,
    df_properties: pd.DataFrame,
    df_views: pd.DataFrame,
    df_containers: pd.DataFrame,
):
    with pd.ExcelWriter(output_file, mode="w") as writer:
        df_metadata.to_excel(writer, sheet_name="Metadata", header=False, index=False)
        df_properties.to_excel(writer, sheet_name="Properties", index=False)
        df_views.to_excel(writer, sheet_name="Views", index=False)
        df_containers.to_excel(writer, sheet_name="Containers", index=False)

    logging.info(
        f"Rules sheet for {df_metadata.loc[df_metadata['Key'] == 'name', 'Value'].item()} has been generated successfully"
    )
