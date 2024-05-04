import logging
import traceback
from typing import cast

from cognite.client import CogniteClient
from cognite.client.data_classes import LabelDefinition, LabelDefinitionList

from cognite.neat.legacy.rules.exporters._core import get_labels
from cognite.neat.legacy.rules.models.rules import Rules


def upload_labels(
    client: CogniteClient,
    rules: Rules,
    data_set_id: int,
    extra_labels: list | None = None,
    stop_on_exception: bool = False,
):
    """Generates labels from transformation rules and upload them to CDF

    Args:
        client : Instance of CogniteClient
        transformation_rules : Instance of TransformationRules which contains the labels to upload
        data_set_id : Id of the dataset to upload the labels to
        extra_labels : Any additional labels not defined in TransformationRules ,
                       by default ["historic", "non-historic"]
        stop_on_exception : If this function fails to stop the process, by default False
    """
    if extra_labels is None:
        extra_labels = []

    try:
        logging.debug("Fetching existing labels from CDF")
        # This is to list all labels, not just the ones in the dataset since labels
        # must have unique external_ids, fixing issue that Daniel encountered
        if retrieved_labels := client.labels.list(limit=-1):
            existing_labels = set(retrieved_labels.to_pandas().external_id)
        else:
            existing_labels = set()
        logging.debug(f"Found {len(existing_labels)} existing labels in CDF")
    except Exception as e:
        logging.debug("Error fetching existing labels from CDF, no ")
        traceback.print_exc()
        if stop_on_exception:
            raise e
        existing_labels = set()

    non_existing_labels = set(list(get_labels(rules)) + extra_labels).difference(existing_labels)

    if non_existing_labels:
        logging.debug(f"Creating total of {len(existing_labels)} new labels in CDF")
        labels = [
            LabelDefinition(external_id=label, name=label, data_set_id=data_set_id) for label in non_existing_labels
        ]
        res = cast(LabelDefinitionList, client.labels.create(labels))
        logging.debug(f"Created total of {len(res)} new labels in CDF")
    else:
        logging.debug("No new labels created in CDF")
