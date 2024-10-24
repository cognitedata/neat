import logging

from pydantic import BaseModel, field_validator, model_validator


class QueryRequest(BaseModel):
    graph_name: str
    workflow_name: str = "default"
    query: str


class RuleRequest(BaseModel):
    graph_name: str
    workflow_name: str = "default"
    rule_type: str
    rule: str


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
