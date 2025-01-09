from typing import Literal

from pydantic import BaseModel


class NeatConfig(BaseModel, validate_assignment=True):
    progress_bar: Literal["tqdm", "rich", "tqdm-notebook", "infer"] | None = "infer"


GLOBAL_CONFIG = NeatConfig()
