from typing import Literal

from pydantic import Field

from ._base import BaseModelObject
from ._constants import DM_EXTERNAL_ID_PATTERN, SPACE_FORMAT_PATTERN


class ContainerReference(BaseModelObject):
    type: Literal["container"] = "container"
    space: str = Field(
        description="Id of the space hosting (containing) the container.",
        min_length=1,
        max_length=43,
        pattern=SPACE_FORMAT_PATTERN,
    )
    external_id: str = Field(
        description="External-id of the container.",
        min_length=1,
        max_length=255,
        pattern=DM_EXTERNAL_ID_PATTERN,
    )
