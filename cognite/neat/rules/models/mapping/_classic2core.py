from ._base import RuleMapping


def create_classic_to_core_mapping() -> RuleMapping:
    return RuleMapping.model_validate(_CLASSIC_TO_CORE)


_CLASSIC_TO_CORE = {
    "classes": [
        {"destination": {"Class": "CogniteAsset"}, "source": {"Class": "Asset"}},
        {"destination": {"Class": "DataProduct"}, "source": {"Class": "DataSet"}},
        {"destination": {"Class": "CogniteActivity"}, "source": {"Class": "Event"}},
        {"destination": {"Class": "CogniteFile"}, "source": {"Class": "File"}},
        {"destination": {"Class": "CogniteTimeSeries"}, "source": {"Class": "TimeSeries"}},
    ],
    "properties": [
        {
            "destination": {"Class": "CogniteAsset", "Property": "externalId"},
            "source": {"Class": "Asset", "Property": "externalId"},
        },
        {
            "destination": {"Class": "CogniteAsset", "Property": "name"},
            "source": {"Class": "Asset", "Property": "name"},
        },
        {
            "destination": {"Class": "CogniteAsset", "Property": "parent"},
            "source": {"Class": "Asset", "Property": "parentId"},
        },
        {
            "destination": {"Class": "CogniteAsset", "Property": "description"},
            "source": {"Class": "Asset", "Property": "description"},
        },
        {
            "destination": {"Class": "CogniteSourceSystem", "Property": "name"},
            "source": {"Class": "Asset", "Property": "source"},
        },
        {
            "destination": {"Class": "CogniteAsset", "Property": "tag"},
            "source": {"Class": "Asset", "Property": "labels"},
        },
        {
            "destination": {"Class": "DataProduct", "Property": "externalId"},
            "source": {"Class": "DataSet", "Property": "externalId"},
        },
        {
            "destination": {"Class": "DataProduct", "Property": "name"},
            "source": {"Class": "DataSet", "Property": "name"},
        },
        {
            "destination": {"Class": "DataProduct", "Property": "description"},
            "source": {"Class": "DataSet", "Property": "description"},
        },
        {
            "destination": {"Class": "DataProduct", "Property": "metadata"},
            "source": {"Class": "DataSet", "Property": "metadata"},
        },
        {
            "destination": {"Class": "DataProduct", "Property": "writeProtected"},
            "source": {"Class": "DataSet", "Property": "writeProtected"},
        },
        {
            "destination": {"Class": "CogniteActivity", "Property": "externalId"},
            "source": {"Class": "Event", "Property": "externalId"},
        },
        {
            "destination": {"Class": "CogniteSchedulable", "Property": "startTime"},
            "source": {"Class": "Event", "Property": "startTime"},
        },
        {
            "destination": {"Class": "CogniteSchedulable", "Property": "endTime"},
            "source": {"Class": "Event", "Property": "endTime"},
        },
        {
            "destination": {"Class": "CogniteActivity", "Property": "description"},
            "source": {"Class": "Event", "Property": "description"},
        },
        {
            "destination": {"Class": "CogniteActivity", "Property": "assets"},
            "source": {"Class": "Event", "Property": "assetIds"},
        },
        {
            "destination": {"Class": "CogniteSourceSystem", "Property": "name"},
            "source": {"Class": "Event", "Property": "source"},
        },
        {
            "destination": {"Class": "CogniteFile", "Property": "externalId"},
            "source": {"Class": "File", "Property": "externalId"},
        },
        {"destination": {"Class": "CogniteFile", "Property": "name"}, "source": {"Class": "File", "Property": "name"}},
        {
            "destination": {"Class": "CogniteFile", "Property": "directory"},
            "source": {"Class": "File", "Property": "directory"},
        },
        {
            "destination": {"Class": "CogniteSourceSystem", "Property": "name"},
            "source": {"Class": "File", "Property": "source"},
        },
        {
            "destination": {"Class": "CogniteFile", "Property": "mimeType"},
            "source": {"Class": "File", "Property": "mimeType"},
        },
        {
            "destination": {"Class": "CogniteFile", "Property": "assets"},
            "source": {"Class": "File", "Property": "assetIds"},
        },
        {
            "destination": {"Class": "CogniteFile", "Property": "sourceCreatedTime"},
            "source": {"Class": "File", "Property": "sourceCreatedTime"},
        },
        {
            "destination": {"Class": "CogniteFile", "Property": "sourceUpdatedTime"},
            "source": {"Class": "File", "Property": "sourceModifiedTime"},
        },
        {
            "destination": {"Class": "CogniteTimeSeries", "Property": "externalId"},
            "source": {"Class": "TimeSeries", "Property": "externalId"},
        },
        {
            "destination": {"Class": "CogniteTimeSeries", "Property": "name"},
            "source": {"Class": "TimeSeries", "Property": "name"},
        },
        {
            "destination": {"Class": "CogniteTimeSeries", "Property": "type"},
            "source": {"Class": "TimeSeries", "Property": "isString"},
        },
        {
            "destination": {"Class": "CogniteTimeSeries", "Property": "sourceUnit"},
            "source": {"Class": "TimeSeries", "Property": "unit"},
        },
        {
            "destination": {"Class": "CogniteTimeSeries", "Property": "unit"},
            "source": {"Class": "TimeSeries", "Property": "unitExternalId"},
        },
        {
            "destination": {"Class": "CogniteTimeSeries", "Property": "assets"},
            "source": {"Class": "TimeSeries", "Property": "assetId"},
        },
        {
            "destination": {"Class": "CogniteTimeSeries", "Property": "isStep"},
            "source": {"Class": "TimeSeries", "Property": "isStep"},
        },
        {
            "destination": {"Class": "CogniteTimeSeries", "Property": "description"},
            "source": {"Class": "TimeSeries", "Property": "description"},
        },
    ],
}
