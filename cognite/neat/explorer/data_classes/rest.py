from pydantic import BaseModel


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


class NodesAndEdgesRequest(BaseModel):
    graph_name: str
    workflow_name: str = "default"
    node_class_filter: list[str]
    src_edge_filter: list[str]
    dst_edge_filter: list[str]
    cache: bool = False
    limit: int = 1000
    node_name_property: str = ""
