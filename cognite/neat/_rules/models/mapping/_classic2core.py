import yaml

from cognite.neat._rules.models.mapping._base import RuleMapping


def create_classic_to_core_mapping(org_name: str) -> RuleMapping:
    raw = """views:
    - destination:
        view: cdf_cdm:CogniteAsset
      source:
        view: {{ org_name }}Asset
    - destination:
        view: cdf_cdm:DataProduct
      source:
        view: {{ org_name }}DataSet
    - destination:
        view: cdf_cdm:CogniteActivity
      source:
        view: {{ org_name }}Event
    - destination:
        view: cdf_cdm:CogniteFile
      source:
        view: {{ org_name }}File
    - destination:
        view: cdf_cdm:CogniteTimeSeries
      source:
        view: {{ org_name }}TimeSeries
    containerProperties:
    - destination:
        container: cdf_cdm:CogniteAsset
        property: externalId
      source:
        container: {{ org_name }}Asset
        property: externalId
    - destination:
        container: cdf_cdm:CogniteAsset
        property: name
      source:
        container: {{ org_name }}Asset
        property: name
    - destination:
        container: cdf_cdm:CogniteAsset
        property: parent
      source:
        container: {{ org_name }}Asset
        property: parentId
    - destination:
        container: cdf_cdm:CogniteAsset
        property: description
      source:
        container: {{ org_name }}Asset
        property: description
    - destination:
        container: cdf_cdm:CogniteSourceSystem
        property: name
      source:
        container: {{ org_name }}Asset
        property: source
    - destination:
        container: cdf_cdm:CogniteAsset
        property: tag
      source:
        container: {{ org_name }}Asset
        property: labels
    - destination:
        container: cdf_cdm:DataProduct
        property: externalId
      source:
        container: {{ org_name }}DataSet
        property: externalId
    - destination:
        container: cdf_cdm:DataProduct
        property: name
      source:
        container: {{ org_name }}DataSet
        property: name
    - destination:
        container: cdf_cdm:DataProduct
        property: description
      source:
        container: {{ org_name }}DataSet
        property: description
    - destination:
        container: cdf_cdm:DataProduct
        property: metadata
      source:
        container: {{ org_name }}DataSet
        property: metadata
    - destination:
        container: cdf_cdm:DataProduct
        property: writeProtected
      source:
        container: {{ org_name }}DataSet
        property: writeProtected
    - destination:
        container: cdf_cdm:CogniteActivity
        property: externalId
      source:
        container: {{ org_name }}Event
        property: externalId
    - destination:
        container: cdf_cdm:CogniteSchedulable
        property: startTime
      source:
        container: {{ org_name }}Event
        property: startTime
    - destination:
        container: cdf_cdm:CogniteSchedulable
        property: endTime
      source:
        container: {{ org_name }}Event
        property: endTime
    - destination:
        container: cdf_cdm:CogniteActivity
        property: description
      source:
        container: {{ org_name }}Event
        property: description
    - destination:
        container: cdf_cdm:CogniteActivity
        property: assets
      source:
        container: {{ org_name }}Event
        property: assetIds
    - destination:
        container: cdf_cdm:CogniteSourceSystem
        property: name
      source:
        container: {{ org_name }}Event
        property: source
    - destination:
        container: cdf_cdm:CogniteFile
        property: externalId
      source:
        container: {{ org_name }}File
        property: externalId
    - destination:
        container: cdf_cdm:CogniteFile
        property: name
      source:
        container: {{ org_name }}File
        property: name
    - destination:
        container: cdf_cdm:CogniteFile
        property: directory
      source:
        container: {{ org_name }}File
        property: directory
    - destination:
        container: cdf_cdm:CogniteSourceSystem
        property: name
      source:
        container: {{ org_name }}File
        property: source
    - destination:
        container: cdf_cdm:CogniteFile
        property: mimeType
      source:
        container: {{ org_name }}File
        property: mimeType
    - destination:
        container: cdf_cdm:CogniteFile
        property: assets
      source:
        container: {{ org_name }}File
        property: assetIds
    - destination:
        container: cdf_cdm:CogniteFile
        property: sourceCreatedTime
      source:
        container: {{ org_name }}File
        property: sourceCreatedTime
    - destination:
        container: cdf_cdm:CogniteFile
        property: sourceUpdatedTime
      source:
        container: {{ org_name }}File
        property: sourceModifiedTime
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        property: externalId
      source:
        container: {{ org_name }}TimeSeries
        property: externalId
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        property: name
      source:
        container: {{ org_name }}TimeSeries
        property: name
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        property: type
      source:
        container: {{ org_name }}TimeSeries
        property: isString
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        property: sourceUnit
      source:
        container: {{ org_name }}TimeSeries
        property: unit
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        property: unit
      source:
        container: {{ org_name }}TimeSeries
        property: unitExternalId
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        property: assets
      source:
        container: {{ org_name }}TimeSeries
        property: assetId
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        property: isStep
        value_type: boolean
      source:
        container: {{ org_name }}TimeSeries
        property: isStep
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        property: description
        value_type: text
      source:
        container: {{ org_name }}TimeSeries
        property: description
    """.replace("{{ org_name }}", org_name)

    return RuleMapping.model_validate(yaml.safe_load(raw))


if __name__ == "__main__":
    create_classic_to_core_mapping("MyOrg")
