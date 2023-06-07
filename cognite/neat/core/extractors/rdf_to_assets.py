import logging
import warnings
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Union
from warnings import warn

import numpy as np
import pandas as pd
from cognite.client import CogniteClient
from cognite.client.data_classes import Asset, AssetHierarchy, AssetList
from deepdiff import DeepDiff
from rdflib import Graph, Namespace
from rdflib.term import URIRef

from cognite.neat.core.data_classes import AssetTemplate, Property
from cognite.neat.core.data_classes.config import EXCLUDE_PATHS
from cognite.neat.core.data_classes.transformation_rules import TransformationRules
from cognite.neat.core.loader.graph_store import NeatGraphStore
from cognite.neat.core.utils import chunker, datetime_utc_now, remove_namespace, retry_decorator

ORPHANAGE = {
    "external_id": "orphanage",
    "name": "Orphanage",
    "parent_external_id": None,
    "description": "Used to store all assets which parent does not exist",
    "metadata": {
        "type": "Orphanage",
        "cdfResourceType": "Asset",
        "identifier": "orphanage",
        "active": "true",
        "start_time": "",
        "update_time": "",
    },
    "data_set_id": None,
    "labels": ["Orphanage", "non-historic"],
}


def _get_class_instance_ids(graph: Graph, class_: str, namespace: Namespace, limit: int = -1) -> List[URIRef]:
    """Get instances ids for a given class

    Parameters
    ----------
    graph : Graph
        Graph containing class instances
    class_ : str
        Class for which instances are to be found
    namespace : Namespace
        Namespace of given class (to avoid writing long URIs)
    limit : int
        Max number of instances to return, by default -1 meaning all instances

    Returns
    -------
    List[URIRef]
        List of class instance URIs
    """

    query_statement = "SELECT DISTINCT ?subject WHERE { ?subject a <class> .} LIMIT X".replace(
        "class", namespace[class_]
    ).replace("LIMIT X", "" if limit == -1 else f"LIMIT {limit}")
    logging.debug(f"Query statement: {query_statement}")
    return [res[0] for res in list(graph.query(query_statement))]


def _get_class_instance(graph: Graph, instance: URIRef) -> List[tuple]:
    """Get instance by means of tuples containing property-value pairs

    Returns
    -------
    List
        list property-value pairs
    """

    query_statement = "SELECT DISTINCT ?predicate ?object WHERE {<subject> ?predicate ?object .}".replace(
        "subject", instance
    )
    result = list(graph.query(query_statement))

    # Adds instance id for sake of keep chain of custody
    result += [(URIRef("http://purl.org/dc/terms/identifier"), instance)]

    return result


def _get_class_property_pairs(transformation_rules: TransformationRules) -> dict[List[Property]]:
    """Define classes in terms of their properties

    Parameters
    ----------
    transformation_rules : TransformationRules
        _description_

    Returns
    -------
    dict
        Dict containing keys as class names and list of their properties
    """

    classes = {}

    for property_ in transformation_rules.properties.keys():
        class_ = transformation_rules.properties[property_].class_name

        if class_ in classes:
            classes[class_] += [transformation_rules.properties[property_]]
        else:
            classes[class_] = [transformation_rules.properties[property_]]

    return classes


def _define_asset_class_mapping(transformation_rules: TransformationRules) -> dict:
    """Define mapping from class to asset properties

    Parameters
    ----------
    transformation_rules : TransformationRules
        Transformation rules

    Returns
    -------
    tuple[dict, dict[Any, dict[str, list[Any]]]]
        Dict containing mapping from class to asset properties
    """
    solution2cdf_mapping_rules = _get_class_property_pairs(transformation_rules)

    asset_class_mapping = {}

    for class_, properties in solution2cdf_mapping_rules.items():
        asset_class_mapping[class_] = {
            "external_id": [],
            "name": [],
            "description": [],
            "parent_external_id": [],
            "metadata": [],
        }

        for property_ in properties:
            if "Asset" in property_.cdf_resource_type and property_.property_name != "*":
                for resource_type_property in property_.resource_type_property:
                    if (
                        resource_type_property in asset_class_mapping[class_]
                        and property_.property_name not in asset_class_mapping[class_][resource_type_property]
                    ):
                        asset_class_mapping[class_][resource_type_property] += [property_.property_name]

                    if property_.property_name not in asset_class_mapping[class_]["metadata"]:
                        asset_class_mapping[class_]["metadata"] += [property_.property_name]

    return asset_class_mapping


def _remap_class_properties(class_instance: dict, asset_class_mapping: dict) -> Tuple[dict, set, set]:
    """Remaps original class instance properties to asset properties (e.g., external_id, name, description, metadata)

    Parameters
    ----------
    class_instance : dict
        Dictionary containing class instance properties and values originating from RDF
        stripped from namespaces
    asset_class_mapping : dict
        Property mapping from class to asset

    Returns
    -------
    Tuple[dict, set, set]
        Remapped class instance, set of missing asset properties and set of missing asset metadata
    """
    # Make distinction between missing properties that map into Asset fields
    # and missing RDF properties that are defined by sheet
    instance_properties = list(class_instance.keys())
    missing_properties = set()

    for property_group, ordered_properties in asset_class_mapping.items():
        if property_group != "metadata" and ordered_properties:
            if matching_property := next(
                (a for a in ordered_properties if a in instance_properties),
                None,
            ):
                class_instance[property_group] = class_instance[matching_property]
            else:
                missing_properties.add(property_group)

    missing_metadata = set(asset_class_mapping["metadata"]).difference(set(instance_properties))

    return class_instance, missing_properties, missing_metadata


def _class2asset_instance(
    class_: str,
    class_instance: dict,
    asset_class_mapping: dict,
    data_set_id: int,
    orphanage_asset_external_id: str = None,
    external_id_prefix: str = None,
    fallback_property: str = "identifier",
    empty_name_default: str = "Missing Name",
    add_missing_metadata: bool = True,
) -> dict:
    """Converts class instance to asset instance dictionary

    Parameters
    ----------
    class_ : str
        Class name which instance is being converted to asset instance
    class_instance : dict
        Dictionary containing class instance properties and values originating from RDF
        stripped from namespaces
    asset_class_mapping : dict
        Property mapping from class to asset
    data_set_id : int
        data set id to which asset belongs
    orphanage_asset_id : str, optional
        Orphanage asset external id, by default None
    external_id_prefix : str, optional
        External id prefix to be added to any external id, by default None
    fallback_property : str, optional
        Property from class instance to be used as fallback in case of missing properties, by default "identifier"


    Returns
    -------
    dict
        Asset instance dictionary
    """

    remapped_class_instance, missing_properties, missing_metadata = _remap_class_properties(
        class_instance, asset_class_mapping
    )

    # setting class instance type to class name
    remapped_class_instance["type"] = class_
    # This will be a default case since we want to use original identifier as external_id
    # We are though dropping namespace from the original identifier (avoiding long-tail URIs)
    if "external_id" in missing_properties or asset_class_mapping["external_id"] == []:
        try:
            __extracted_from___class2asset_instance_49(
                remapped_class_instance,
                fallback_property,
                "external_id",
                class_,
            )
        except Exception:
            __extracted_from___class2asset_instance_56(fallback_property, class_, remapped_class_instance)
    # This should not be the use case however to still have name of the object we are using
    # fallback property here as well (typically identifier)
    if "name" in missing_properties:
        try:
            __extracted_from___class2asset_instance_49(remapped_class_instance, fallback_property, "name", class_)
        except Exception:
            __extracted_from___class2asset_instance_56(fallback_property, class_, remapped_class_instance)
    # If object is expected to have parent, but parent is not provided, it is added to orphanage
    # This is typically sign of objects not following proposed ontology/data model/schema
    if "parent_external_id" in missing_properties and orphanage_asset_external_id:
        remapped_class_instance["parent_external_id"] = orphanage_asset_external_id

    if "name" in remapped_class_instance and remapped_class_instance["name"] == "":
        remapped_class_instance["name"] = empty_name_default

    # To maintain shape across of all assets of specific type we are adding missing metadata
    # keys as empty strings, this was request by Statnett
    # Generally this is bad practice, but more of a workaround of their bad data
    if missing_metadata and add_missing_metadata:
        msg = f"Adding missing metadata keys with values set to empty string for {class_}"
        msg += f" instance <{remapped_class_instance['identifier']}>. "
        logging.debug(msg)
        for key in missing_metadata:
            remapped_class_instance[key] = ""
            logging.debug(f"\tKey {key} added to <{remapped_class_instance['identifier']}> metadata!")

    asset_instance = AssetTemplate(
        **remapped_class_instance, external_id_prefix=external_id_prefix, data_set_id=data_set_id
    )

    # Removing field external_id_prefix from asset instance dictionary as it is only
    # convenience field for external_id and parent_external_id update in AssetTemplate
    return asset_instance.dict(exclude={"external_id_prefix"})


# TODO Rename this here and in `__class2asset_instance`
def __extracted_from___class2asset_instance_49(remapped_class_instance, fallback_property, arg2, class_):
    remapped_class_instance[arg2] = remapped_class_instance[fallback_property]
    msg = f"Missing external_id for {class_} instance <{remapped_class_instance['identifier']}>. "
    msg += f"Using value <{remapped_class_instance[fallback_property]}> provided "
    msg += f"by property <{fallback_property}>!"

    logging.debug(msg)


# TODO Rename this here and in `__class2asset_instance`
def __extracted_from___class2asset_instance_56(fallback_property, class_, remapped_class_instance):
    msg = f"Fallback property <{fallback_property}> not found for {class_} "
    msg += f"instance <{remapped_class_instance['identifier']}>."
    logging.error(msg)
    raise ValueError(msg)


def _list2dict(class_instance: list) -> dict:
    """Converting list of class instance properties and values to dictionary

    Parameters
    ----------
    class_instance : list
        Class instance properties and values originating from RDF as list of tuples

    Returns
    -------
    dict
        Class instance properties and values as dictionary
    """

    class_instance_dict = {}
    for property_value_pair in class_instance:
        property_ = remove_namespace(property_value_pair[0])

        # Remove namespace from URIRef values, otherwise convert Literal to string
        # ideally this should react upon property type provided in sheet
        # however Assets only support string values
        value = (
            remove_namespace(property_value_pair[1])
            if isinstance(property_value_pair[1], URIRef)
            else str(property_value_pair[1])
        )

        if property_ in class_instance_dict and value not in class_instance_dict[property_]:
            class_instance_dict[property_] = (
                class_instance_dict[property_] + [value]
                if isinstance(class_instance_dict[property_], list)
                else [class_instance_dict[property_], value]
            )
        else:
            class_instance_dict[property_] = value

    return class_instance_dict


def rdf2assets(
    graph_store: NeatGraphStore,
    transformation_rules: TransformationRules,
    stop_on_exception: bool = False,
    use_orphanage: bool = True,
) -> dict[str, Asset]:
    """Creates assets from RDF graph

    Parameters
    ----------
    graph : Graph
        Graph containing RDF data
    transformation_rules : TransformationRules
        Instance of TransformationRules class containing transformation rules

    Returns
    -------
    Dict[str, Asset]
        Dictionary of assets with external_id as key
    """

    orphanage_asset_external_id = (
        f"{transformation_rules.metadata.externalIdPrefix or ''}orphanage-{transformation_rules.metadata.data_set_id}"
    )

    graph = graph_store.get_graph()
    # Step 1: Create rdf to asset property mapping
    logging.info("Generating rdf to asset property mapping")
    asset_class_mapping = _define_asset_class_mapping(transformation_rules)

    # Step 4: Get ids of classes
    logging.info("Get ids of instances of classes")
    assets: dict[str, Asset] = {}
    class_ids = {
        class_: _get_class_instance_ids(graph, class_, transformation_rules.metadata.namespace)
        for class_ in asset_class_mapping
    }
    # Step 5: Create Assets based on class instances
    logging.info("Create Assets based on class instances")
    for class_ in asset_class_mapping:
        # TODO: Rename class_id to instance_id
        class_ns = transformation_rules.metadata.namespace[class_]
        logging.debug(f"Processing class <{class_ns}> . Number of instances: {len(class_ids[class_])}")
        progress_counter = 0
        # loading all instances into cache
        try:
            query = f"SELECT ?instance ?prop ?value WHERE {{ ?instance rdf:type <{class_ns}> . ?instance ?prop ?value . }} order by ?instance "
            logging.info(query)
            response_df = graph_store.query_to_dataframe(query)
        except Exception as e:
            logging.error(f"Error while loading instances of class <{class_ns}> into cache. Reason: {e}")
            # traceback.print_exc()
            if stop_on_exception:
                raise e
            continue

        grouped_df = response_df.groupby("instance")

        for instance_id, group_df in grouped_df:
            try:
                instance_property_values = group_df.filter(items=["property", "value"]).values.tolist()
                instance_property_values += [(URIRef("http://purl.org/dc/terms/identifier"), URIRef(instance_id))]

                # this will strip namespace from property names and values
                class_instance = _list2dict(instance_property_values)

                # class instance is repaired and converted to asset dictionary
                asset = _class2asset_instance(
                    class_,
                    class_instance,
                    asset_class_mapping[class_],
                    transformation_rules.metadata.data_set_id,
                    orphanage_asset_external_id if use_orphanage else None,  # we need only base external id
                    transformation_rules.metadata.externalIdPrefix or None,
                )

                # adding labels and timestamps
                asset["labels"] = [asset["metadata"]["type"], "non-historic"]
                asset["metadata"]["start_time"] = str(datetime.now(timezone.utc))
                asset["metadata"]["update_time"] = str(datetime.now(timezone.utc))

                # log every 10000 assets
                if progress_counter % 10000 == 0:
                    logging.info(" Next 10000 Assets processed")

                assets[asset["external_id"]] = asset
                progress_counter += 1
            except Exception as ValidationError:
                logging.error(
                    f"Skipping class <{class_}> instance <{remove_namespace(instance_id)}>, reason:\n{ValidationError}\n"
                )
                if stop_on_exception:
                    raise ValidationError

        logging.debug(f"Class <{class_}> processed")

    if orphanage_asset_external_id not in assets:
        _extracted_from_rdf2asset_dictionary_95(orphanage_asset_external_id, transformation_rules, assets)
    logging.info("Assets dictionary created")

    return assets


def rdf2asset_dictionary(
    graph_store: NeatGraphStore,
    transformation_rules: TransformationRules,
    stop_on_exception: bool = False,
    use_orphanage: bool = True,
) -> Dict[str, Asset]:
    warn("'rdf2asset_dictionary' is deprecated, please use 'rdf2assets' instead!")
    logging.warning("'rdf2asset_dictionary' is deprecated, please use 'rdf2assets' instead!")
    return rdf2assets(graph_store, transformation_rules, stop_on_exception, use_orphanage)


# TODO Rename this here and in `rdf2asset_dictionary`
def _extracted_from_rdf2asset_dictionary_95(orphanage_asset_external_id, transformation_rules, assets):
    print(f"Orphanage with external id {orphanage_asset_external_id} not found in asset hierarchy!")
    logging.warning(f"Orphanage with external id {orphanage_asset_external_id} not found in asset hierarchy!")
    logging.warning(f"Adding default orphanage with external id {orphanage_asset_external_id}")

    # updating default external id for orphanage in case there are additional prefix to be added
    ORPHANAGE["external_id"] = orphanage_asset_external_id
    ORPHANAGE["data_set_id"] = transformation_rules.metadata.data_set_id
    ORPHANAGE["metadata"]["start_time"] = str(datetime_utc_now())
    ORPHANAGE["metadata"]["update_time"] = str(datetime_utc_now())
    assets[orphanage_asset_external_id] = ORPHANAGE


def _asset2dict(asset: Asset) -> dict:
    """Return asset as dict representation

    Parameters
    ----------
    asset : Asset
        Instance of Asset class

    Returns
    -------
    dict
        Asset in dict representation
    """

    return {
        "external_id": asset.external_id,
        "name": asset.name,
        "description": asset.description,
        "parent_external_id": asset.parent_external_id,
        "data_set_id": asset.data_set_id,
        "metadata": asset.metadata,
    }


def _flatten_labels(labels: List[Dict[str, str]]) -> set[str]:
    """Flatten labels"""
    return {label["externalId"] for label in labels}


def _is_historic(labels) -> bool:
    """Check if asset is historic"""
    return "historic" in labels


def _categorize_cdf_assets(
    client: CogniteClient, data_set_id: int, partitions: int
) -> Tuple[Optional[pd.DataFrame], dict[str, set]]:
    """Categorize CDF assets

    Parameters
    ----------
    client : CogniteClient
        Instance of CogniteClient
    data_set_id : int
        Id of data set
    partitions : int
        Number of partitions

    Returns
    -------
    Tuple[Optional[pd.DataFrame], dict]
        CDF assets as pandas dataframe and dictionary with categorized assets
    """
    cdf_assets = client.assets.list(data_set_ids=data_set_id, limit=None, partitions=partitions).to_pandas()

    logging.info(f"Number of assets in CDF {len(cdf_assets)} that have been fetched")

    if cdf_assets.empty:
        return None, {"non-historic": set(), "historic": set()}
    if "labels" not in cdf_assets:
        # Add empty list for labels column.
        cdf_assets["labels"] = np.empty((len(cdf_assets), 0)).tolist()

    cdf_columns = set(cdf_assets.columns)
    expected_columns = {"external_id", "labels", "parent_external_id", "data_set_id", "name", "description", "metadata"}

    cdf_assets = cdf_assets[list(expected_columns.intersection(cdf_columns))]
    cdf_assets = cdf_assets.where(pd.notnull(cdf_assets), None)
    cdf_assets["labels"] = cdf_assets["labels"].apply(_flatten_labels).values  # type: ignore
    cdf_assets["is_historic"] = cdf_assets.labels.apply(_is_historic).values

    categorized_asset_ids = {
        "historic": set(cdf_assets[cdf_assets.is_historic].external_id.values),
        "non-historic": set(cdf_assets[~cdf_assets.is_historic].external_id.values),
    }

    cdf_assets.drop(["is_historic"], axis=1, inplace=True)
    msg = f"CDF assets categorized into {len(categorized_asset_ids['historic'])} historic"
    msg += f" and {len(categorized_asset_ids['non-historic'])} non-historic assets"
    logging.info(msg)

    return cdf_assets, categorized_asset_ids


def order_assets(assets: dict[str, dict]) -> list[Asset]:
    """Order assets in a way that parent assets are created before child assets

    Parameters
    ----------
    assets : dict[str, dict]
        List of assets to be created

    Returns
    -------
    list[Asset]
        Ordered list of assets
    """
    hierarchy = AssetHierarchy([Asset(**asset) for asset in assets.values()], ignore_orphans=True)
    insert_dct = hierarchy.groupby_parent_xid()
    subtree_count = hierarchy.count_subtree(insert_dct)

    hierarchy = None

    asset_creation_order = pd.DataFrame.from_dict(subtree_count, orient="index", columns=["order"]).sort_values(
        by="order", ascending=False
    )
    asset_creation_order["external_id"] = asset_creation_order.index

    hierarchy = AssetList([Asset(**asset) for asset in assets.values()]).to_pandas()
    hierarchy = hierarchy.where(pd.notnull(hierarchy), None)
    hierarchy = hierarchy.merge(asset_creation_order, left_on="external_id", right_on="external_id")
    hierarchy = hierarchy.sort_values(by="order", ascending=False)
    hierarchy.reset_index(drop=True, inplace=True)
    hierarchy.labels = hierarchy.labels.apply(_flatten_labels)
    hierarchy.drop(["order"], axis=1, inplace=True)

    return [Asset(**row.to_dict()) for _, row in hierarchy.iterrows()]


def _assets_to_create(rdf_assets: dict, asset_ids: set) -> list[Asset]:
    """Return list of assets to be created

    Parameters
    ----------
    rdf_assets : dict
        Dictionary containing assets derived from knowledge graph (RDF)
    asset_ids : set
        Set of asset ids to be created

    Returns
    -------
    list[Asset]
        Ordered list of assets to be created
    """
    start_time = datetime_utc_now()
    if asset_ids:
        logging.info("Wrangling assets to be created into their final form")
        ordered_assets = order_assets({external_id: rdf_assets[external_id] for external_id in asset_ids})

        logging.info(f"Wrangling completed in {(datetime_utc_now() - start_time).seconds} seconds")
        return ordered_assets
    return []


def _assets_to_update(
    rdf_assets: dict,
    cdf_assets: pd.DataFrame,
    asset_ids: set,
    exclude_paths: list = EXCLUDE_PATHS,
    stop_on_exception: bool = False,
) -> tuple[list[Asset], dict[str, dict]]:
    """Return list of assets to be updated

    Parameters
    ----------
    rdf_assets : dict
        Dictionary containing assets derived from knowledge graph (RDF)
    cdf_assets : pd.DataFrame
        Dataframe containing assets from CDF
    asset_ids : set
        Candidate assets to be updated
    exclude_paths : list, optional
        Paths not to be checked when diffing rdf and cdf assets, by default EXCLUDE_PATHS
    stop_on_exception: bool, optional
        Whether to stop on exception or not, by default False

    Returns
    -------
    tuple[list[Asset], dict[str, dict]]
        List of assets to be updated and detailed report of changes per asset
    """

    start_time = datetime_utc_now()
    assets = []
    report = {}
    if not asset_ids:
        return [], {}
    logging.info("Wrangling assets to be updated into their final form")
    cdf_asset_subset = {
        row["external_id"]: row
        for row in cdf_assets[cdf_assets["external_id"].isin(asset_ids)].to_dict(orient="records")
    }
    for external_id in asset_ids:
        cdf_asset = cdf_asset_subset[external_id]
        diffing_result = DeepDiff(cdf_asset, rdf_assets[external_id], exclude_paths=exclude_paths)

        if "parent_external_id" in diffing_result.affected_root_keys:
            msg = f"Asset <{external_id}> is changing its parent from <{cdf_asset['parent_external_id']}>"
            msg += f" to <{rdf_assets[external_id]['parent_external_id']}>! This is not allowed!"
            if stop_on_exception:
                logging.error(msg)
                raise ValueError(msg)
            else:
                msg += " Skipping update of this asset!"
                logging.warning(msg)
                warnings.warn(
                    msg,
                    stacklevel=2,
                )
                continue

        if diffing_result and "root['metadata']['active']" not in diffing_result.affected_paths:
            asset = Asset(**rdf_assets[external_id])
            try:
                asset.metadata["start_time"] = cdf_asset[external_id]["metadata"]["start_time"]
            except KeyError:
                asset.metadata["start_time"] = str(datetime.now(timezone.utc))
            asset.metadata["update_time"] = str(datetime.now(timezone.utc))
            assets.append(asset)

            report[external_id] = dict(diffing_result)

    logging.info(f"Wrangling of {len(assets)} completed in {(datetime_utc_now() - start_time).seconds} seconds")
    return assets, report


def _assets_to_resurrect(rdf_assets: dict, cdf_assets: pd.DataFrame, asset_ids: set) -> list[Asset]:
    """Returns list of assets to be resurrected

    Parameters
    ----------
    rdf_assets : dict
        Dictionary containing assets derived from knowledge graph (RDF)
    cdf_assets : pd.DataFrame
        Dataframe containing assets from CDF
    asset_ids : set
        Set of asset ids to be resurrected

    Returns
    -------
    list[Asset]
        List of assets to be resurrected
    """
    start_time = datetime_utc_now()
    assets = []
    if not asset_ids:
        return []
    logging.info("Wrangling assets to be resurrected into their final form")
    cdf_asset_subset = {
        row["external_id"]: row
        for row in cdf_assets[cdf_assets["external_id"].isin(asset_ids)].to_dict(orient="records")
    }
    for external_id in asset_ids:
        cdf_asset = cdf_asset_subset[external_id]

        asset = Asset(**rdf_assets[external_id])

        try:
            asset.metadata["start_time"] = cdf_asset[external_id]["metadata"]["start_time"]
        except KeyError:
            asset.metadata["start_time"] = str(datetime.now(timezone.utc))
        asset.metadata["update_time"] = str(datetime.now(timezone.utc))
        asset.metadata["resurrection_time"] = str(datetime.now(timezone.utc))
        assets.append(asset)

    logging.info(f"Wrangling of {len(assets)} completed in {(datetime_utc_now() - start_time).seconds} seconds")
    return assets


def _assets_to_decommission(cdf_assets, asset_ids) -> list[Asset]:
    start_time = datetime_utc_now()

    assets = []
    if not asset_ids:
        return []
    logging.info("Wrangling assets to be decommissioned into their final form")
    cdf_asset_subset = {
        row["external_id"]: row
        for row in cdf_assets[cdf_assets["external_id"].isin(asset_ids)].to_dict(orient="records")
    }

    for external_id in asset_ids:
        cdf_asset = cdf_asset_subset[external_id]

        cdf_asset["metadata"]["update_time"] = str(datetime.now(timezone.utc))
        cdf_asset["metadata"].pop("resurrection_time", None)
        cdf_asset["metadata"]["end_time"] = str(datetime.now(timezone.utc))
        cdf_asset["metadata"]["active"] = "false"
        try:
            cdf_asset["labels"].remove("non-historic")
        except KeyError:
            logging.info(f"Asset {external_id} missed label 'non-historic'")
        cdf_asset["labels"].add("historic")

        assets.append(Asset(**cdf_asset))

    logging.info(f"Wrangling completed in {(datetime_utc_now() - start_time).seconds} seconds")
    return assets


def categorize_assets(
    client: CogniteClient,
    rdf_assets: dict,
    data_set_id: int,
    partitions: int = 2,
    stop_on_exception: bool = False,
    return_report: bool = False,
) -> Union[tuple[dict, dict], dict]:
    """Categorize assets on those that are to be created, updated and decommissioned

    Parameters
    ----------
    client : CogniteClient
        Instance of CogniteClient
    rdf_assets : dict
        Dictionary containing asset external_id - asset pairs
    data_set_id : int
        Dataset id to which assets are to be/are stored
    partitions : int, optional
        Number of partitions to use when fetching assets from CDF, by default 2
    stop_on_exception : bool, optional
        Whether to stop on exception or not, by default False
    return_report : bool, optional
        Whether to report on the diffing results or not, by default False

    Returns
    -------
    Dict[str, list]
        dictionary containing asset category - list of asset pairs
    """
    # TODO: Cache categorized assets somewhere instead of creating them

    cdf_assets, categorized_asset_ids = _categorize_cdf_assets(client, data_set_id, partitions)

    rdf_asset_ids = set(rdf_assets.keys())

    # ids to create
    create_ids = rdf_asset_ids.difference(
        categorized_asset_ids["historic"].union(categorized_asset_ids["non-historic"])
    )

    # ids potentially to update
    update_ids = rdf_asset_ids.intersection(categorized_asset_ids["non-historic"])

    # ids to decommission
    decommission_ids = categorized_asset_ids["non-historic"].difference(rdf_asset_ids)

    # ids to resurrect
    resurrect_ids = categorized_asset_ids["historic"].intersection(rdf_asset_ids)

    logging.info(f"Number of assets to create: { len(create_ids)}")
    logging.info(f"Number of assets to potentially update: { len(update_ids)}")
    logging.info(f"Number of assets to decommission: { len(decommission_ids)}")
    logging.info(f"Number of assets to resurrect: { len(resurrect_ids)}")

    report = {"create": create_ids, "resurrect": resurrect_ids, "decommission": decommission_ids, "update": None}
    categorized_assets = {
        "create": _assets_to_create(rdf_assets, create_ids),
        "update": (_assets_to_update(rdf_assets, cdf_assets, update_ids, stop_on_exception=stop_on_exception))[0],
        "resurrect": _assets_to_resurrect(rdf_assets, cdf_assets, resurrect_ids),
        "decommission": _assets_to_decommission(cdf_assets, decommission_ids),
    }

    return (categorized_assets, report) if return_report else categorized_assets


def _micro_batch_push(
    client: CogniteClient,
    assets: list,
    batch_size: int = 1000,
    push_type: str = "update",
    message: str = "Updated",
    max_retries: int = 1,
    retry_delay: int = 5,
):
    """Updates assets in batches of 1000

    Parameters
    ----------
    client : CogniteClient
        Instance of CogniteClient
    assets : list
        List of assets to be created or updated
    batch_size : int, optional
        Size of batch, by default 1000
    push_type : str, optional
        Type of push, either "update" or "create", by default "update"
    message : str, optional
        Message to logged, by default "Updated"
    """
    total = len(assets)
    counter = 0
    if push_type not in ["update", "create"]:
        logging.info(f"push_type {push_type} not supported")
        raise ValueError(f"push_type {push_type} not supported")
    for batch in chunker(assets, batch_size):
        counter += len(batch)
        start_time = datetime_utc_now()

        @retry_decorator(max_retries=max_retries, retry_delay=retry_delay, component_name="microbatch-assets")
        def upsert_assets(batch):
            if push_type == "update":
                client.assets.update(batch)
            elif push_type == "create":
                client.assets.create_hierarchy(batch)

        upsert_assets(batch)

        delta_time = (datetime_utc_now() - start_time).seconds

        msg = f"{message} {counter} of {total} assets, batch processing time: {delta_time:.2f} "
        msg += f"seconds ETC: {delta_time * (total - counter) / (60*batch_size) :.2f} minutes"
        logging.info(msg)


def upload_assets(
    client: CogniteClient,
    categorized_assets: Dict[str, Sequence[Asset]],
    batch_size: int = 5000,
    max_retries: int = 1,
    retry_delay: int = 3,
):
    """Uploads categorized assets to CDF

    Parameters
    ----------
    client : CogniteClient
        Instance of CogniteClient
    categorized_assets : Dict[str, list]
        dictionary containing asset category - list of asset pairs
    batch_size : int, optional
        Size of batch, by default 5000
    """
    if batch_size:
        logging.info(f"Uploading assets in batches of {batch_size}")
        if categorized_assets["create"]:
            _micro_batch_push(
                client,
                categorized_assets["create"],
                batch_size,
                push_type="create",
                message="Created",
                max_retries=max_retries,
                retry_delay=retry_delay,
            )

        if categorized_assets["update"]:
            _micro_batch_push(
                client,
                categorized_assets["update"],
                batch_size,
                message="Updated",
                max_retries=max_retries,
                retry_delay=retry_delay,
            )

        if categorized_assets["resurrect"]:
            _micro_batch_push(
                client,
                categorized_assets["resurrect"],
                batch_size,
                message="Resurrected",
                max_retries=max_retries,
                retry_delay=retry_delay,
            )

        if categorized_assets["decommission"]:
            _micro_batch_push(
                client,
                categorized_assets["decommission"],
                batch_size,
                message="Decommissioned",
                max_retries=max_retries,
                retry_delay=retry_delay,
            )

    else:
        logging.info("Batch size not set, pushing all assets to CDF in one go!")

        @retry_decorator(max_retries=max_retries, retry_delay=retry_delay, component_name="create-assets")
        def create_assets():
            if categorized_assets["create"]:
                client.assets.create_hierarchy(categorized_assets["create"])

            if categorized_assets["update"]:
                client.assets.create_hierarchy(categorized_assets["update"], upsert=True, upsert_mode="replace")

            if categorized_assets["resurrect"]:
                client.assets.create_hierarchy(categorized_assets["resurrect"], upsert=True, upsert_mode="replace")

            if categorized_assets["decommission"]:
                client.assets.create_hierarchy(categorized_assets["decommission"], upsert=True, upsert_mode="replace")

        create_assets()


def remove_non_existing_labels(client: CogniteClient, assets: Sequence[Asset]) -> Sequence[Asset]:
    cdf_labels = client.labels.list(limit=-1)
    if not cdf_labels:
        # No labels, nothing to check.
        return assets

    available_labels = {label.external_id for label in cdf_labels}
    cleaned_assets = []
    for asset in assets:
        if asset.labels:
            asset.labels = [label for label in asset.labels if label.external_id in available_labels]
        cleaned_assets.append(asset)

    return cleaned_assets
