from typing import Literal

from pydantic import BaseModel


class NeatConfig(BaseModel, validate_assignment=True):
    progress_bare: Literal["tqdm", "rich", "infer"] | None = "infer"


GLOBAL_CONFIG = NeatConfig()
