import logging
import warnings

# import traceback
from typing import Dict, List, Set, Union
from warnings import warn

import pandas as pd
from cognite.client import CogniteClient
from cognite.client.data_classes import LabelFilter, Relationship, RelationshipUpdate
from cognite.client.exceptions import CogniteDuplicatedError

from cognite.neat.graph.loaders.core.models import RelationshipDefinition, RelationshipDefinitions
from cognite.neat.graph.loaders.core.rdf_to_assets import _categorize_cdf_assets
from cognite.neat.graph.extractors.graph_store import NeatGraphStore
from cognite.neat.rules.models import TransformationRules
from cognite.neat.utils.utils import chunker, datetime_utc_now, epoch_now_ms, remove_namespace, retry_decorator


def define_relationships(rules: TransformationRules, stop_on_exception: bool = False) -> RelationshipDefinitions:
    relationships = {}

    # Unique ids used to check for redefinitions of relationships
    ids = set()

    for row, rule in rules.properties.items():
        if "Relationship" in rule.cdf_resource_type:
            relationship = RelationshipDefinition(
                source_class=rule.class_id,
                target_class=rule.expected_value_type,
                property_=rule.property_id,
                labels=list(
                    set([rule.label, rule.class_id, rule.expected_value_type, "non-historic", rule.property_id])
                ),
                target_type=rule.target_type,
                source_type=rule.source_type,
                relationship_external_id_rule=rule.relationship_external_id_rule,
            )

            id_ = f"{rule.class_id}({rule.property_id})"
            if id_ in ids:
                msg = f"Relationship {rule.property_id} redefined at {row} in transformation rules!"
                if stop_on_exception:
                    logging.error(msg)
                    raise ValueError(msg)
                else:
                    msg += " Skipping redefinition!"
                    warnings.warn(msg, stacklevel=2)
                    logging.warning(msg)
            else:
                relationships[row] = relationship
                ids.add(id_)

    if relationships:
        return RelationshipDefinitions(
            data_set_id=rules.metadata.data_set_id,
            prefix=rules.metadata.prefix,
            namespace=rules.metadata.namespace,
            relationships=relationships,
        )

    msg = "No relationship defined in transformation rule sheet!"
    if stop_on_exception:
        logging.error(msg)
        raise ValueError(msg)
    else:
        warnings.warn(msg, stacklevel=2)
        logging.warning(msg)
        return RelationshipDefinitions(
            data_set_id=rules.metadata.data_set_id,
            prefix=rules.metadata.prefix,
            namespace=rules.metadata.namespace,
            relationships={},
        )


# should be renamed to rdf2relationship_data_frame -> rdf2relationships
def rdf2relationships(
    graph_store: NeatGraphStore,
    transformation_rules: TransformationRules,
    stop_on_exception: bool = False,
) -> pd.DataFrame:
    """_summary_

    Parameters
    ----------
    graph : Graph
        _description_
    transformation_rules : TransformationRules
        _description_

    Returns
    -------
    Dict[str, Asset]
        _description_
    """

    # Step 1: Generate relationship definitions
    relationship_definitions = define_relationships(transformation_rules, stop_on_exception)

    # Step 2: Generation relationships

    query_statement_template_by_reference = """
    SELECT ?source ?target
    WHERE {
        ?source a prefix:source_class .
        ?target a prefix:target_class .
        ?source prefix:property_ ?target
    }"""

    query_statement_template_by_value = """
    SELECT ?source_id ?target_id
    WHERE {
        ?source a prefix:source_class .
        ?source prefix:property_ ?target .
        ?source prefix:source_ext_id_prop_name ?source_id .
        ?target a prefix:target_class .
        ?target prefix:target_ext_id_prop_name ?target_id .
    }
    """

    relationship_data_frames = []
    for id_, definition in relationship_definitions.relationships.items():
        try:
            logging.debug("Processing relationship: " + id_)
            external_id_prop_name = definition.relationship_external_id_rule
            if external_id_prop_name:
                query = (
                    query_statement_template_by_value.replace("prefix", relationship_definitions.prefix)
                    .replace("source_ext_id_prop_name", external_id_prop_name)
                    .replace("target_ext_id_prop_name", external_id_prop_name)
                    .replace("source_class", definition.source_class)
                    .replace("target_class", definition.target_class)
                    .replace("property_", definition.property_)
                )
            else:
                query = (
                    query_statement_template_by_reference.replace("prefix", relationship_definitions.prefix)
                    .replace("source_class", definition.source_class)
                    .replace("target_class", definition.target_class)
                    .replace("property_", definition.property_)
                )

            logging.debug("Rel query: " + query)
            relationship_data_frame = pd.DataFrame(list(graph_store.query(query)))
            relationship_data_frame.rename(columns={0: "source_external_id", 1: "target_external_id"}, inplace=True)

            # removes namespace
            relationship_data_frame = relationship_data_frame.applymap(remove_namespace)

            # adding prefix
            if transformation_rules.metadata.externalIdPrefix:
                relationship_data_frame["source_external_id"] = (
                    transformation_rules.metadata.externalIdPrefix + relationship_data_frame["source_external_id"]
                )
                relationship_data_frame["target_external_id"] = (
                    transformation_rules.metadata.externalIdPrefix + relationship_data_frame["target_external_id"]
                )

            relationship_data_frame["target_type"] = definition.target_type
            relationship_data_frame["source_type"] = definition.source_type

            # to make sure that by default we set Relationship to active, i.e. non-historic)
            relationship_data_frame["labels"] = [definition.labels] * len(relationship_data_frame)

            # set default external id
            relationship_data_frame["external_id"] = (
                relationship_data_frame["source_external_id"] + ":" + relationship_data_frame["target_external_id"]
            )
            relationship_data_frame["data_set_id"] = transformation_rules.metadata.data_set_id
            relationship_data_frames += [relationship_data_frame]
        except Exception as e:
            logging.error("Error processing relationship: " + id_)
            # traceback.print_exc()
            if stop_on_exception:
                raise e
            continue

    if relationship_data_frames:
        relationship_data_frames = pd.concat(relationship_data_frames)
        relationship_data_frames.reset_index(inplace=True, drop=True)

        # Remove duplicate rows, if any. This should not happen, but it is better to be safe than sorry
        relationship_data_frames.drop_duplicates(subset=["external_id"], inplace=True)

        # Remove duplicate rows, if any. This should not happen, but it is better to be safe than sorry
        relationship_data_frames.drop_duplicates(subset=["external_id"], inplace=True)
        return relationship_data_frames
    else:
        return pd.DataFrame(
            columns=[
                "source_external_id",
                "target_external_id",
                "target_type",
                "source_type",
                "labels",
                "external_id",
                "data_set_id",
            ]
        )


def rdf2relationship_data_frame(
    graph_store: NeatGraphStore,
    transformation_rules: TransformationRules,
    stop_on_exception: bool = False,
) -> pd.DataFrame:
    warn("'rdf2relationship_data_frame' is deprecated, please use 'rdf2relationships' instead!")
    logging.warning("'rdf2relationship_data_frame' is deprecated, please use 'rdf2relationships' instead!")
    return rdf2relationships(graph_store, transformation_rules, stop_on_exception)


def _filter_relationship_xids(relationship_data_frame: pd.DataFrame, asset_xids: Union[List, Set]) -> Set:
    return set(
        relationship_data_frame[
            (relationship_data_frame["source_external_id"].isin(asset_xids))
            | (relationship_data_frame["target_external_id"].isin(asset_xids))
        ]["external_id"]
    )


def _categorize_rdf_relationship_xids(rdf_relationships: pd.DataFrame, categorized_asset_ids: dict) -> Dict[str, set]:
    """Categorizes the external ids of the RDF relationship."""

    missing_asset_ids = (
        set(rdf_relationships.target_external_id)
        .union(rdf_relationships.source_external_id)
        .difference(categorized_asset_ids["historic"].union(categorized_asset_ids["non-historic"]))
    )

    if missing_asset_ids:
        msg = f"Relationships are referring to these assets {missing_asset_ids}, which are missing in CDF."
        msg += "Relationships will not be created for assets that are missing in CDF."
        msg += "Please make sure that all assets are present in CDF before creating relationships."
        logging.warning(msg)

    # First mask all relationships which contain assets that do not exist in CDF
    mask_impossible = _filter_relationship_xids(rdf_relationships, missing_asset_ids)

    # Then mask all relationships which contain assets that are historic while masking
    # all impossible relationships
    mask_historic = _filter_relationship_xids(rdf_relationships, categorized_asset_ids["historic"]).difference(
        mask_impossible
    )

    mask_non_historic = (
        _filter_relationship_xids(rdf_relationships, categorized_asset_ids["non-historic"])
        .difference(mask_historic)
        .difference(mask_impossible)
    )

    return {"impossible": mask_impossible, "historic": mask_historic, "non-historic": mask_non_historic}


def _get_label_based_cdf_relationship_xids(client, data_set_id, labels, partitions) -> set:
    """Get external ids of relationships in CDF for a given data set filtered on labels"""

    labels = LabelFilter(contains_any=labels) if labels is not None else None
    relationship_data_frame = client.relationships.list(
        data_set_ids=data_set_id, limit=-1, labels=labels, partitions=partitions
    ).to_pandas()
    return set() if relationship_data_frame.empty else set(relationship_data_frame.external_id)


def _categorize_cdf_relationship_xids(client, data_set_id, partitions) -> dict[str, set]:
    return {
        "historic": _get_label_based_cdf_relationship_xids(client, data_set_id, ["historic"], partitions),
        "non-historic": _get_label_based_cdf_relationship_xids(client, data_set_id, ["non-historic"], partitions),
    }


def _relationship_to_create(relationships: pd.DataFrame) -> List[Relationship]:
    start_time = datetime_utc_now()
    if relationships.empty:
        return []
    logging.info("Wrangling assets to be created into their final form")
    relationship_list = [Relationship(**row) for row in relationships.to_dict(orient="records")]
    logging.info(f"Wrangling completed in {(datetime_utc_now() - start_time).seconds} seconds")
    return relationship_list


def _relationships_to_decommission(external_ids: list[str]) -> list[RelationshipUpdate]:
    start_time = datetime_utc_now()
    relationships = []
    if not external_ids:
        return []

    logging.info("Wrangling relationships to be decommissioned into their final form")

    for external_id in external_ids:
        # Create relationship update object instance
        relationship = RelationshipUpdate(external_id=external_id)

        # Remove "non-historic" label and add "historic" label
        relationship.labels.remove("non-historic")
        relationship.labels.add(["historic"])

        # Set end time of relationships
        relationship.end_time.set(epoch_now_ms())

        # Add relationship to list of relationship updates
        relationships += [relationship]

    logging.info(f"Wrangling of {len(relationships)} completed in {(datetime_utc_now() - start_time).seconds} seconds")
    return relationships


def _relationships_to_resurrect(external_ids: list[str]) -> list[RelationshipUpdate]:
    start_time = datetime_utc_now()
    relationships = []
    if not external_ids:
        return []

    logging.info("Wrangling relationships to be resurrected into their final form")

    for external_id in external_ids:
        # Create relationship update object instance
        relationship = RelationshipUpdate(external_id=external_id)

        # Remove "non-historic" label and add "historic" label
        relationship.labels.remove("historic")
        relationship.labels.add(["non-historic"])

        # Set end time of relationships
        relationship.end_time.set(None)

        # Add relationship to list of relationship updates
        relationships += [relationship]

    logging.info(f"Wrangling of {len(relationships)} completed in {(datetime_utc_now() - start_time).seconds} seconds")
    return relationships


def categorize_relationships(
    client: CogniteClient,
    rdf_relationships: pd.DataFrame,
    data_set_id: int,
    partitions: int = 40,
    return_report: bool = False,
) -> Union[
    tuple[dict[str, list[Union[Relationship, RelationshipUpdate]]], dict[str, set]],
    dict[str, list[Union[Relationship, RelationshipUpdate]]],
]:
    """Categorize relationships on those that are to be created, decommissioned or resurrected"""
    # TODO also figure out which relationships to be deleted

    _, categorized_asset_ids = _categorize_cdf_assets(client, data_set_id=data_set_id, partitions=partitions)
    categorized_rdf_relationships = _categorize_rdf_relationship_xids(rdf_relationships, categorized_asset_ids)
    categorized_cdf_relationships = _categorize_cdf_relationship_xids(client, data_set_id, partitions=partitions)

    cdf_relationships_all = categorized_cdf_relationships["historic"].union(
        categorized_cdf_relationships["non-historic"]
    )
    rdf_relationships_all = categorized_rdf_relationships["historic"].union(
        categorized_rdf_relationships["non-historic"]
    )

    # relationships to create
    # NonHistoric_rdf - (Historic_cdf ∪ Non-historic_cdf)
    create_xids = categorized_rdf_relationships["non-historic"].difference(cdf_relationships_all)

    # relationships to decommission
    # rdf: Historic_rdf ∩ NonHistoric_cdf ∪ (All_cdf - All_rdf)
    decommission_xids = (
        categorized_rdf_relationships["historic"]
        .intersection(categorized_cdf_relationships["non-historic"])
        .union(categorized_cdf_relationships["non-historic"].difference(rdf_relationships_all))
    )

    # relationships to resurrect
    # NonHistoric_rdf ∩ Historic_cdf
    resurrect_xids = categorized_rdf_relationships["non-historic"].intersection(
        categorized_cdf_relationships["historic"]
    )

    logging.info(f"Number of relationships to create: { len(create_xids)}")
    logging.info(f"Number of relationships to decommission: { len(decommission_xids)}")
    logging.info(f"Number of relationships to resurrect: { len(resurrect_xids)}")

    report = {"create": create_xids, "resurrect": resurrect_xids, "decommission": decommission_xids}
    categorized_relationships = {
        "create": _relationship_to_create(rdf_relationships[rdf_relationships.external_id.isin(create_xids)]),
        "resurrect": _relationships_to_resurrect(resurrect_xids),
        "decommission": _relationships_to_decommission(decommission_xids),
    }

    return (categorized_relationships, report) if return_report else categorized_relationships


def _micro_batch_push(
    client: CogniteClient,
    relationships: list,
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
    relationships : list
        List of relationships to be created or updated
    batch_size : int, optional
        Size of batch, by default 1000
    push_type : str, optional
        Type of push, either "update" or "create", by default "update"
    message : str, optional
        Message to logged, by default "Updated"
    """
    total = len(relationships)
    counter = 0
    if push_type not in ["update", "create"]:
        logging.info(f"push_type {push_type} not supported")
        raise ValueError(f"push_type {push_type} not supported")

    for batch in chunker(relationships, batch_size):
        counter += len(batch)
        start_time = datetime_utc_now()

        @retry_decorator(max_retries=max_retries, retry_delay=retry_delay, component_name="microbatch-relationships")
        def update_relationships(batch):
            if push_type == "update":
                client.relationships.update(batch)
            elif push_type == "create":
                client.relationships.create(batch)

        try:
            update_relationships(batch)
        except CogniteDuplicatedError as e:
            # This situation should not happen but if it does, we need to handle it
            exists = {d["externalId"] for d in e.duplicated}
            missing_relationships = [t for t in batch if t.external_id not in exists]
            client.relationships.create(missing_relationships)

        delta_time = (datetime_utc_now() - start_time).seconds

        msg = f"{message} {counter} of {total} relationships, batch processing time: {delta_time:.2f} "
        msg += f"seconds ETC: {delta_time * (total - counter) / (60*batch_size) :.2f} minutes"
        logging.info(msg)


def upload_relationships(
    client: CogniteClient,
    categorized_relationships: Dict[str, list[Union[Relationship, RelationshipUpdate]]],
    batch_size: int = 5000,
    max_retries: int = 1,
    retry_delay: int = 3,
):
    """Uploads categorized relationships to CDF

    Parameters
    ----------
    client : CogniteClient
        Instance of CogniteClient
    categorized_relationships : Dict[str, list[Union[Relationship, RelationshipUpdate]]]
        Categories of relationships to be uploaded
    batch_size : int, optional
        Size of batch, by default 5000
    """
    if batch_size:
        logging.info(f"Uploading relationships in batches of {batch_size}")
        if categorized_relationships["create"]:
            _micro_batch_push(
                client,
                categorized_relationships["create"],
                batch_size,
                push_type="create",
                message="Created",
                max_retries=max_retries,
                retry_delay=retry_delay,
            )

        if categorized_relationships["resurrect"]:
            _micro_batch_push(
                client,
                categorized_relationships["resurrect"],
                batch_size,
                message="Resurrected",
                max_retries=max_retries,
                retry_delay=retry_delay,
            )

        if categorized_relationships["decommission"]:
            _micro_batch_push(
                client,
                categorized_relationships["decommission"],
                batch_size,
                message="Decommissioned",
                max_retries=max_retries,
                retry_delay=retry_delay,
            )

    else:
        logging.info("Batch size not set, pushing all relationships to CDF in one go!")

        @retry_decorator(max_retries=max_retries, retry_delay=retry_delay, component_name="create-relationships")
        def create_relationships():
            if categorized_relationships["create"]:
                client.relationships.create(categorized_relationships["create"])

            if categorized_relationships["resurrect"]:
                client.relationships.update(categorized_relationships["resurrect"])

            if categorized_relationships["decommission"]:
                client.relationships.update(categorized_relationships["decommission"])

        try:
            create_relationships()
        except CogniteDuplicatedError as e:
            # This situation should not happen but if it does, the code attempts to handle it
            exists = {d["externalId"] for d in e.duplicated}
            missing_relationships = [t for t in categorized_relationships["create"] if t.external_id not in exists]
            client.relationships.create(missing_relationships)
