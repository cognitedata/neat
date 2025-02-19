from cognite.client import CogniteClient
from cognite.client.data_classes import data_modeling
from cognite.client.exceptions import CogniteAPIError
from cognite.neat._cfihos.common.log import log_init

logging = log_init(f"{__name__}", "i")


def create_or_update_space(cdf_client: CogniteClient, space: str, description: str) -> str:
    """
    Creates or updates a space in Cognite Data Fusion (CDF). This function attempts to create a new space or update
    an existing space with the provided description.

    Args:
        cdf_client (CogniteClient): The Cognite client.
        space (str): The identifier for the space to be created or updated.
        description (str): A description for the space.

    Returns:
        str: The identifier of the created or updated space.


    Notes:
        - This function constructs a SpaceApply object with the specified space identifier and description, and applies it using the Cognite client.
    """
    try:
        space = cdf_client.data_modeling.spaces.apply(
            data_modeling.SpaceApply(
                space=space,
                name=space,
                description=description,
            )
        )
        logging.info(f"Created or updated space '{space.space}'")
        return space.space

    except CogniteAPIError as e:
        logging.error(f"Failed to create or update space '{space}': {e}")
        raise e
