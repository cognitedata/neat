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
        Property: externalId
      source:
        container: {{ org_name }}Asset
        Property: externalId
    - destination:
        container: cdf_cdm:CogniteAsset
        Property: name
      source:
        container: {{ org_name }}Asset
        Property: name
    - destination:
        container: cdf_cdm:CogniteAsset
        Property: parent
      source:
        container: {{ org_name }}Asset
        Property: parentId
    - destination:
        container: cdf_cdm:CogniteAsset
        Property: description
      source:
        container: {{ org_name }}Asset
        Property: description
    - destination:
        container: cdf_cdm:CogniteSourceSystem
        Property: name
      source:
        container: {{ org_name }}Asset
        Property: source
    - destination:
        container: cdf_cdm:CogniteAsset
        Property: tag
      source:
        container: {{ org_name }}Asset
        Property: labels
    - destination:
        container: cdf_cdm:DataProduct
        Property: externalId
      source:
        container: {{ org_name }}DataSet
        Property: externalId
    - destination:
        container: cdf_cdm:DataProduct
        Property: name
      source:
        container: {{ org_name }}DataSet
        Property: name
    - destination:
        container: cdf_cdm:DataProduct
        Property: description
      source:
        container: {{ org_name }}DataSet
        Property: description
    - destination:
        container: cdf_cdm:DataProduct
        Property: metadata
      source:
        container: {{ org_name }}DataSet
        Property: metadata
    - destination:
        container: cdf_cdm:DataProduct
        Property: writeProtected
      source:
        container: {{ org_name }}DataSet
        Property: writeProtected
    - destination:
        container: cdf_cdm:CogniteActivity
        Property: externalId
      source:
        container: {{ org_name }}Event
        Property: externalId
    - destination:
        container: cdf_cdm:CogniteSchedulable
        Property: startTime
      source:
        container: {{ org_name }}Event
        Property: startTime
    - destination:
        container: cdf_cdm:CogniteSchedulable
        Property: endTime
      source:
        container: {{ org_name }}Event
        Property: endTime
    - destination:
        container: cdf_cdm:CogniteActivity
        Property: description
      source:
        container: {{ org_name }}Event
        Property: description
    - destination:
        container: cdf_cdm:CogniteActivity
        Property: assets
      source:
        container: {{ org_name }}Event
        Property: assetIds
    - destination:
        container: cdf_cdm:CogniteSourceSystem
        Property: name
      source:
        container: {{ org_name }}Event
        Property: source
    - destination:
        container: cdf_cdm:CogniteFile
        Property: externalId
      source:
        container: {{ org_name }}File
        Property: externalId
    - destination:
        container: cdf_cdm:CogniteFile
        Property: name
      source:
        container: {{ org_name }}File
        Property: name
    - destination:
        container: cdf_cdm:CogniteFile
        Property: directory
      source:
        container: {{ org_name }}File
        Property: directory
    - destination:
        container: cdf_cdm:CogniteSourceSystem
        Property: name
      source:
        container: {{ org_name }}File
        Property: source
    - destination:
        container: cdf_cdm:CogniteFile
        Property: mimeType
      source:
        container: {{ org_name }}File
        Property: mimeType
    - destination:
        container: cdf_cdm:CogniteFile
        Property: assets
      source:
        container: {{ org_name }}File
        Property: assetIds
    - destination:
        container: cdf_cdm:CogniteFile
        Property: sourceCreatedTime
      source:
        container: {{ org_name }}File
        Property: sourceCreatedTime
    - destination:
        container: cdf_cdm:CogniteFile
        Property: sourceUpdatedTime
      source:
        container: {{ org_name }}File
        Property: sourceModifiedTime
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        Property: externalId
      source:
        container: {{ org_name }}TimeSeries
        Property: externalId
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        Property: name
      source:
        container: {{ org_name }}TimeSeries
        Property: name
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        Property: type
      source:
        container: {{ org_name }}TimeSeries
        Property: isString
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        Property: sourceUnit
      source:
        container: {{ org_name }}TimeSeries
        Property: unit
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        Property: unit
      source:
        container: {{ org_name }}TimeSeries
        Property: unitExternalId
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        Property: assets
      source:
        container: {{ org_name }}TimeSeries
        Property: assetId
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        Property: isStep
      source:
        container: {{ org_name }}TimeSeries
        Property: isStep
    - destination:
        container: cdf_cdm:CogniteTimeSeries
        Property: description
      source:
        container: {{ org_name }}TimeSeries
        Property: description
    """.replace("{{ org_name }}", org_name)

    return RuleMapping.model_validate(yaml.safe_load(raw))


if __name__ == "__main__":
    create_classic_to_core_mapping("MyOrg")
