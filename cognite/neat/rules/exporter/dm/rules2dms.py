"""Exports rules to CDF Data Model Storage.
"""

from typing import Optional
from pydantic import BaseModel, Field, model_validator, field_validator

from cognite.client import CogniteClient

from cognite.client.data_classes.data_modeling import ContainerApply, ContainerProperty, Text


class DataModel(BaseModel):
    space: str
    external_id: str
    version: str
    description: Optional[str] = None
    name: Optional[str] = None
    containers: list[ContainerApply]

    @classmethod
    def from_rules(cls, rules):
        ...

    def to_cdf(self, client: CogniteClient):
        # create space if it is missing
        # create data model if it is missing
        # create containers if they are missing
        # create properties if they are missing
        ...

    def create_space(self, client: CogniteClient):
        ...

    def create_data_model(self, client: CogniteClient):
        ...

    def create_containers(self, client: CogniteClient):
        ...
