SPACE_FORMAT_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_-]{0,41}[a-zA-Z0-9]?$"
DM_EXTERNAL_ID_PATTERN = r"^[a-zA-Z]([a-zA-Z0-9_]{0,253}[a-zA-Z0-9])?$"
CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,253}[a-zA-Z0-9]?$"
FORBIDDEN_SPACES = frozenset(["space", "cdf", "dms", "pg3", "shared", "system", "node", "edge"])
FORBIDDEN_CONTAINER_AND_VIEW_EXTERNAL_IDS = frozenset(
    [
        "Query",
        "Mutation",
        "Subscription",
        "String",
        "Int32",
        "Int64",
        "Int",
        "Float32",
        "Float64",
        "Float",
        "Timestamp",
        "JSONObject",
        "Date",
        "Numeric",
        "Boolean",
        "PageInfo",
        "File",
        "Sequence",
        "TimeSeries",
    ]
)
FORBIDDEN_CONTAINER_AND_VIEW_PROPERTIES_IDENTIFIER = frozenset(
    [
        "space",
        "externalId",
        "createdTime",
        "lastUpdatedTime",
        "deletedTime",
        "edge_id",
        "node_id",
        "project_id",
        "property_group",
        "seq",
        "tg_table_name",
        "extensions",
    ]
)
