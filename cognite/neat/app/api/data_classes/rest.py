import logging

from pydantic import BaseModel, field_validator, model_validator
from cognite.neat.rules.models.domain import DomainMetadata, DomainProperty, DomainClass
from cognite.neat.rules.models.information import (
    InformationMetadata,
    InformationProperty,
    InformationClass,
)
from cognite.neat.rules.models.dms import DMSMetadata, DMSProperty, DMSView, DMSContainer
from cognite.neat.rules.models import RoleTypes


class QueryRequest(BaseModel):
    graph_name: str
    workflow_name: str = "default"
    query: str


class RuleRequest(BaseModel):
    graph_name: str
    workflow_name: str = "default"
    rule_type: str
    rule: str


class UploadToCdfRequest(BaseModel):
    file_name: str = ""
    file_type: str = "workflow"
    comments: str = ""
    author: str = ""
    tag: str = ""


class DownloadFromCdfRequest(BaseModel):
    file_name: str = ""
    file_type: str = "workflow"
    version: str = ""


class LoadGraphRequest(BaseModel):
    graph_source_template_name: str
    source_location: str


class RunWorkflowRequest(BaseModel):
    name: str
    config: dict
    start_step: str
    sync: bool = False

    @field_validator("config", mode="before")
    def empty_string_to_dict(cls, value):
        if value == "":
            return {}
        return value

    @model_validator(mode="before")
    def log_call(cls, values):
        logging.info(f"RunWorkflowRequest: {values}")
        return values


class NodesAndEdgesRequest(BaseModel):
    graph_name: str
    workflow_name: str = "default"
    node_class_filter: list[str]
    src_edge_filter: list[str]
    dst_edge_filter: list[str]
    cache: bool = False
    limit: int = 1000
    node_name_property: str = ""
    sparql_query: str = ""


class DatatypePropertyRequest(BaseModel):
    graph_name: str = "source"
    workflow_name: str = ""
    cache: bool = False
    limit: int = 10


class TransformationRulesUpdateRequest(BaseModel):
    file_name: str = ""
    output_format: str = "excel"
    rules_object: dict = {}


class NewRuleV2Request(BaseModel):
    role: RoleTypes
    base_data_model: str
    name: str
    description: str
    rule_file: str


class RuleV2MetadataUpsertRequest(BaseModel):
    role: RoleTypes
    rule_file: str
    rule_component: DomainMetadata | InformationMetadata | DMSMetadata


class RuleV2PropertyUpsertRequest(BaseModel):
    role: RoleTypes
    rule_file: str
    rule_component: DomainProperty | InformationProperty | DMSProperty


class RulesV2ClassUpsertRequest(BaseModel):
    role: RoleTypes
    rule_file: str
    rule_component: DomainClass | InformationClass


class RulesV2DMSComponentsUpsertRequest(BaseModel):
    role: RoleTypes
    rule_file: str
    rule_component_name: str
    rule_component: DMSView | DMSContainer
