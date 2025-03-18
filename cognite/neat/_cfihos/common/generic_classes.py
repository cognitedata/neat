from enum import Enum


# Entity Fields
class EntityStructure:
    ID: str = "entityId"
    NAME: str = "entityName"
    DESCRIPTION: str = "description"
    INHERITS_FROM_NAME: str = "inheritsFromName"
    INHERITS_FROM_ID: str = "inheritsFromId"
    FULL_INHERITANCE: str = "fullInheritance"
    PROPERTIES: str = "properties"
    FCC_PREFIX = "FCC_"
    FIRSTCLASSCITIZEN = "firstClassCitizen"


# Property Fields
class PropertyStructure:
    ID: str = "propertyId"
    NAME: str = "propertyName"
    DESCRIPTION: str = "description"
    TARGET_TYPE: str = "targetType"
    PROPERTY_TYPE: str = "propertyType"
    MULTI_VALUED: str = "multiValued"
    IS_REQUIRED: str = "isRequired"
    IS_UNIQUE: str = "isUnique"
    ENUMERATION_TABLE: str = "enumerationTableName"
    UOM: str = "unitOfMeasure"
    PROPERTY_GROUP: str = "propertyGroup"
    INHERITED: str = "inherited"
    INHERITED_FROM: str = "inheritedFrom"
    FIRSTCLASSCITIZEN = "firstClassCitizen"
    MAPPED_PROPERTY = "mapped_property"
    CUSTOM_PROPERTY = "custom_property"
    FCC_PREFIX = "fcc_"
    UNIQUE_ENTITYID_PROPERTYID = "entityIdPropertyId"
    UNIQUE_VALIDATION_ID = "unique_validation_id"
    EDGE_DIRECTION = "edgeDirection"
    EDGE_SOURCE = "edgeSource"
    EDGE_TARGET = "edgeTarget"
    EDGE_EXTERNAL_ID = "edgeExternalId"
    ENTITY_EDGE = "entityEdge"
    Direct_Relation = "DirectRelation"


class GitHubAttributes:
    CFIHOS_EPC_GIT_BRANCH: str = "CFIHOS_EPC_GIT_BRANCH"


class DataSource(Enum):
    CDF = "cdf"
    CSV = "csv"
    GITHUB = "github"

    @classmethod
    def default(cls):
        return cls.CSV

    @classmethod
    def get(cls, value):
        # lowercase for simplicity
        return cls.__members__.get(value.lower(), cls.default())


class ScopeConfig:
    ALL: str = "All"
    TAGS: str = "Tags"
    EQUIPMENT: str = "Equipment"
    SCOPED: str = "Scoped"
