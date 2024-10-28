from ._base import RuleMapping


def create_classic_to_core_mapping() -> RuleMapping:
    return RuleMapping.model_validate(_CLASSIC_TO_CORE)


_CLASSIC_TO_CORE = {
    "classes": [
        {"destination": {"Class": "cdf_cdm:CogniteAsset"}, "source": {"Class": "classic:Asset"}},
        {"destination": {"Class": "cdf_cdm:DataProduct"}, "source": {"Class": "classic:DataSet"}},
        {"destination": {"Class": "cdf_cdm:CogniteActivity"}, "source": {"Class": "classic:Event"}},
        {"destination": {"Class": "cdf_cdm:CogniteFile"}, "source": {"Class": "classic:File"}},
        {"destination": {"Class": "cdf_cdm:CogniteTimeSeries"}, "source": {"Class": "classic:TimeSeries"}},
    ],
    "properties": [
        {
            "destination": {"Class": "cdf_cdm:CogniteAsset", "Property": "externalId"},
            "source": {"Class": "classic:Asset", "Property": "externalId"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteAsset", "Property": "name"},
            "source": {"Class": "classic:Asset", "Property": "name"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteAsset", "Property": "parent"},
            "source": {"Class": "classic:Asset", "Property": "parentId"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteAsset", "Property": "description"},
            "source": {"Class": "classic:Asset", "Property": "description"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteSourceSystem", "Property": "name"},
            "source": {"Class": "classic:Asset", "Property": "source"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteAsset", "Property": "tag"},
            "source": {"Class": "classic:Asset", "Property": "labels"},
        },
        {
            "destination": {"Class": "cdf_cdm:DataProduct", "Property": "externalId"},
            "source": {"Class": "classic:DataSet", "Property": "externalId"},
        },
        {
            "destination": {"Class": "cdf_cdm:DataProduct", "Property": "name"},
            "source": {"Class": "classic:DataSet", "Property": "name"},
        },
        {
            "destination": {"Class": "cdf_cdm:DataProduct", "Property": "description"},
            "source": {"Class": "classic:DataSet", "Property": "description"},
        },
        {
            "destination": {"Class": "cdf_cdm:DataProduct", "Property": "metadata"},
            "source": {"Class": "classic:DataSet", "Property": "metadata"},
        },
        {
            "destination": {"Class": "cdf_cdm:DataProduct", "Property": "writeProtected"},
            "source": {"Class": "classic:DataSet", "Property": "writeProtected"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteActivity", "Property": "externalId"},
            "source": {"Class": "classic:Event", "Property": "externalId"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteSchedulable", "Property": "startTime"},
            "source": {"Class": "classic:Event", "Property": "startTime"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteSchedulable", "Property": "endTime"},
            "source": {"Class": "classic:Event", "Property": "endTime"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteActivity", "Property": "description"},
            "source": {"Class": "classic:Event", "Property": "description"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteActivity", "Property": "assets"},
            "source": {"Class": "classic:Event", "Property": "assetIds"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteSourceSystem", "Property": "name"},
            "source": {"Class": "classic:Event", "Property": "source"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteFile", "Property": "externalId"},
            "source": {"Class": "classic:File", "Property": "externalId"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteFile", "Property": "name"},
            "source": {"Class": "classic:File", "Property": "name"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteFile", "Property": "directory"},
            "source": {"Class": "classic:File", "Property": "directory"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteSourceSystem", "Property": "name"},
            "source": {"Class": "classic:File", "Property": "source"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteFile", "Property": "mimeType"},
            "source": {"Class": "classic:File", "Property": "mimeType"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteFile", "Property": "assets"},
            "source": {"Class": "classic:File", "Property": "assetIds"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteFile", "Property": "sourceCreatedTime"},
            "source": {"Class": "classic:File", "Property": "sourceCreatedTime"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteFile", "Property": "sourceUpdatedTime"},
            "source": {"Class": "classic:File", "Property": "sourceModifiedTime"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteTimeSeries", "Property": "externalId"},
            "source": {"Class": "classic:TimeSeries", "Property": "externalId"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteTimeSeries", "Property": "name"},
            "source": {"Class": "classic:TimeSeries", "Property": "name"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteTimeSeries", "Property": "type"},
            "source": {"Class": "classic:TimeSeries", "Property": "isString"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteTimeSeries", "Property": "sourceUnit"},
            "source": {"Class": "classic:TimeSeries", "Property": "unit"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteTimeSeries", "Property": "unit"},
            "source": {"Class": "classic:TimeSeries", "Property": "unitExternalId"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteTimeSeries", "Property": "assets"},
            "source": {"Class": "classic:TimeSeries", "Property": "assetId"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteTimeSeries", "Property": "isStep"},
            "source": {"Class": "classic:TimeSeries", "Property": "isStep"},
        },
        {
            "destination": {"Class": "cdf_cdm:CogniteTimeSeries", "Property": "description"},
            "source": {"Class": "classic:TimeSeries", "Property": "description"},
        },
    ],
}
