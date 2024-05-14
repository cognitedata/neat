MORE_THAN_ONE_NONE_ALPHANUMERIC_REGEX = r"([_-]{2,})"
PREFIX_COMPLIANCE_REGEX = r"^([a-zA-Z]+)([a-zA-Z0-9]*[_-]{0,1}[a-zA-Z0-9_-]*)([a-zA-Z0-9]*)$"

VIEW_ID_COMPLIANCE_REGEX = (
    r"(?!^(Query|Mutation|Subscription|String|Int32|Int64|Int|Float32|Float64|Float|"
    r"Timestamp|JSONObject|Date|Numeric|Boolean|PageInfo|File|Sequence|TimeSeries)$)"
    r"(^[a-zA-Z][a-zA-Z0-9_]{0,253}[a-zA-Z0-9]?$)"
)
DMS_PROPERTY_ID_COMPLIANCE_REGEX = (
    r"(?!^(space|externalId|createdTime|lastUpdatedTime|deletedTime|edge_id|"
    r"node_id|project_id|property_group|seq|tg_table_name|extensions)$)"
    r"(^[a-zA-Z][a-zA-Z0-9_]{0,253}[a-zA-Z0-9]?$)"
)
CLASS_ID_COMPLIANCE_REGEX = r"(?!^(Class|class)$)(^[a-zA-Z][a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]?$)"
PROPERTY_ID_COMPLIANCE_REGEX = r"^(\*)|(?!^(Property|property)$)(^[a-zA-Z][a-zA-Z0-9._-]{0,253}[a-zA-Z0-9]?$)"
VERSION_COMPLIANCE_REGEX = r"^[a-zA-Z0-9]([.a-zA-Z0-9_-]{0,41}[a-zA-Z0-9])?$"
