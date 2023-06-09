import logging
import traceback

from cognite.client import CogniteClient
from cognite.client.data_classes import LabelDefinition

from cognite.neat.core.rules.models import TransformationRules


def upload_labels(
    client: CogniteClient,
    transformation_rules: TransformationRules,
    extra_labels: list = None,
    stop_on_exception: bool = False,
):
    """Upload labels to CDF

    Parameters
    ----------
    client : CogniteClient
        Instance of CogniteClient
    transformation_rules : TransformationRules
        Instance of TransformationRules which contains the labels to upload
    extra_labels : list[str], optional
        Any additional labels not defined in TransformationRules , by default ["historic", "non-historic"]
    stop_on_exception : bool, optional
        If this function fails to stop the process, by default False
    """
    if extra_labels is None:
        extra_labels = []

    try:
        logging.debug("Fetching existing labels from CDF")
        # This is to list all labels, not just the ones in the dataset since labels
        # must have unique external_ids, fixing issue that Daniel encountered
        if existing_labels := client.labels.list(limit=-1):
            existing_labels = set(existing_labels.to_pandas().external_id)
        else:
            existing_labels = {}
        logging.debug(f"Found {len(existing_labels)} existing labels in CDF")
    except Exception as e:
        logging.debug("Error fetching existing labels from CDF, no ")
        traceback.print_exc()
        if stop_on_exception:
            raise e
        existing_labels = {}

    non_existing_labels = set(list(transformation_rules.get_labels()) + extra_labels).difference(existing_labels)

    labels = []
    if non_existing_labels:
        logging.debug(f"Creating total of {len(existing_labels)} new labels in CDF")
        labels = [
            LabelDefinition(external_id=label, name=label, data_set_id=transformation_rules.metadata.data_set_id)
            for label in non_existing_labels
        ]
        res = client.labels.create(labels)
        logging.debug(f"Created total of {len(res)} new labels in CDF")
    else:
        logging.debug("No new labels created in CDF")
