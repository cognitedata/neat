from cognite.neat._cfihos.common.generic_classes import (
    EntityStructure,
    PropertyStructure,
)

# DMS
MODEL_VERSION_LENGTH = 4
MAX_DMS_MODEL_NAME = 50 + MODEL_VERSION_LENGTH
MAX_DMS_FIELD_NAME = 50 + MODEL_VERSION_LENGTH
CONTAINER_PROPERTY_LIMIT = 100


# Schema Validation Rules
REQ_PROP_STRUCTURE = {
    "description": "Required Model Property Structure",
    "type": "object",
    "properties": {
        PropertyStructure.ID: {"type": "string"},
        PropertyStructure.NAME: {"type": "string"},
        PropertyStructure.DESCRIPTION: {"type": "string"},
        PropertyStructure.PROPERTY_TYPE: {"type": "string"},
        PropertyStructure.TARGET_TYPE: {"type": "string"},
        PropertyStructure.ENUMERATION_TABLE: {"type": ["string", "null"]},
        PropertyStructure.UOM: {"type": ["string", "null"]},
        PropertyStructure.IS_REQUIRED: {"type": "boolean"},
        PropertyStructure.IS_UNIQUE: {"type": "boolean"},
        PropertyStructure.MULTI_VALUED: {"type": "boolean"},
    },
    "required": [
        PropertyStructure.ID,
        PropertyStructure.NAME,
        PropertyStructure.DESCRIPTION,
        PropertyStructure.PROPERTY_TYPE,
        PropertyStructure.TARGET_TYPE,
        PropertyStructure.ENUMERATION_TABLE,
        PropertyStructure.UOM,
        PropertyStructure.IS_REQUIRED,
        PropertyStructure.IS_UNIQUE,
        PropertyStructure.MULTI_VALUED,
    ],
}

REQ_ENTITY_STRUCTURE = {
    "description": "Required Model Entity Structure",
    "type": "object",
    "properties": {
        EntityStructure.ID: {"type": "string"},
        EntityStructure.NAME: {"type": "string"},
        EntityStructure.DESCRIPTION: {"type": "string"},
        EntityStructure.INHERITS_FROM_ID: {
            "type": ["array", "null"],
            "items": {"type": ["string", "null"]},
        },
        EntityStructure.INHERITS_FROM_NAME: {
            "type": ["array", "null"],
            "items": {"type": ["string", "null"]},
        },
        EntityStructure.PROPERTIES: {"type": "array", "items": REQ_PROP_STRUCTURE},
    },
    "required": [
        EntityStructure.ID,
        EntityStructure.NAME,
        EntityStructure.DESCRIPTION,
        EntityStructure.INHERITS_FROM_ID,
        EntityStructure.INHERITS_FROM_NAME,
        EntityStructure.PROPERTIES,
    ],
}

REQ_MODEL_STRUCTURE = {
    "description": "Required Model Structure",
    "type": "object",
    "additionalProperties": REQ_ENTITY_STRUCTURE,
}
