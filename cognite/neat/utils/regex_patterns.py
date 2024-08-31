import re
from functools import cached_property

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


# This pattern ignores commas inside brackets
SPLIT_ON_COMMA_PATTERN = re.compile(r",(?![^(]*\))")
# This pattern ignores equal signs inside brackets
SPLIT_ON_EQUAL_PATTERN = re.compile(r"=(?![^(]*\))")


class _Patterns:
    @cached_property
    def more_than_one_alphanumeric(self) -> re.Pattern:
        return re.compile(MORE_THAN_ONE_NONE_ALPHANUMERIC_REGEX)

    @cached_property
    def prefix_compliance(self) -> re.Pattern[str]:
        return re.compile(PREFIX_COMPLIANCE_REGEX)

    @cached_property
    def view_id_compliance(self) -> re.Pattern[str]:
        return re.compile(VIEW_ID_COMPLIANCE_REGEX)

    @cached_property
    def dms_property_id_compliance(self) -> re.Pattern[str]:
        return re.compile(DMS_PROPERTY_ID_COMPLIANCE_REGEX)

    @cached_property
    def class_id_compliance(self) -> re.Pattern[str]:
        return re.compile(CLASS_ID_COMPLIANCE_REGEX)

    @cached_property
    def property_id_compliance(self) -> re.Pattern[str]:
        return re.compile(PROPERTY_ID_COMPLIANCE_REGEX)

    @cached_property
    def version_compliance(self) -> re.Pattern[str]:
        return re.compile(VERSION_COMPLIANCE_REGEX)


PATTERNS = _Patterns()
