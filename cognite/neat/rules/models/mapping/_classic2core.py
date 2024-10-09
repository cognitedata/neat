from ._base import RuleMapping


def create_classic_to_core_mapping() -> RuleMapping:
    return RuleMapping.model_validate(_CLASSIC_TO_CORE)


_CLASSIC_TO_CORE = {
    "classes": [
        {"destination": {"class_": "CogniteAsset"}, "source": {"class_": "Asset"}},
        {"destination": {"class_": "DataProduct"}, "source": {"class_": "DataSet"}},
        {"destination": {"class_": "CogniteActivity"}, "source": {"class_": "Event"}},
        {"destination": {"class_": "CogniteFile"}, "source": {"class_": "File"}},
        {"destination": {"class_": "CogniteTimeSeries"}, "source": {"class_": "TimeSeries"}},
    ],
    "properties": [
        {
            "destination": {"class_": "CogniteAsset", "property_": "externalId"},
            "source": {"class_": "Asset", "property_": "externalId"},
        },
        {
            "destination": {"class_": "CogniteAsset", "property_": "name"},
            "source": {"class_": "Asset", "property_": "name"},
        },
        {
            "destination": {"class_": "CogniteAsset", "property_": "parent"},
            "source": {"class_": "Asset", "property_": "parentId"},
        },
        {
            "destination": {"class_": "CogniteAsset", "property_": "description"},
            "source": {"class_": "Asset", "property_": "description"},
        },
        {
            "destination": {"class_": "CogniteSourceSystem", "property_": "name"},
            "source": {"class_": "Asset", "property_": "source"},
        },
        {
            "destination": {"class_": "CogniteAsset", "property_": "tag"},
            "source": {"class_": "Asset", "property_": "labels"},
        },
        {
            "destination": {"class_": "DataProduct", "property_": "externalId"},
            "source": {"class_": "DataSet", "property_": "externalId"},
        },
        {
            "destination": {"class_": "DataProduct", "property_": "name"},
            "source": {"class_": "DataSet", "property_": "name"},
        },
        {
            "destination": {"class_": "DataProduct", "property_": "description"},
            "source": {"class_": "DataSet", "property_": "description"},
        },
        {
            "destination": {"class_": "DataProduct", "property_": "metadata"},
            "source": {"class_": "DataSet", "property_": "metadata"},
        },
        {
            "destination": {"class_": "DataProduct", "property_": "writeProtected"},
            "source": {"class_": "DataSet", "property_": "writeProtected"},
        },
        {
            "destination": {"class_": "CogniteActivity", "property_": "externalId"},
            "source": {"class_": "Event", "property_": "externalId"},
        },
        {
            "destination": {"class_": "CogniteSchedulable", "property_": "startTime"},
            "source": {"class_": "Event", "property_": "startTime"},
        },
        {
            "destination": {"class_": "CogniteSchedulable", "property_": "endTime"},
            "source": {"class_": "Event", "property_": "endTime"},
        },
        {
            "destination": {"class_": "CogniteActivity", "property_": "description"},
            "source": {"class_": "Event", "property_": "description"},
        },
        {
            "destination": {"class_": "CogniteActivity", "property_": "assets"},
            "source": {"class_": "Event", "property_": "assetIds"},
        },
        {
            "destination": {"class_": "CogniteSourceSystem", "property_": "name"},
            "source": {"class_": "Event", "property_": "source"},
        },
        {
            "destination": {"class_": "CogniteFile", "property_": "externalId"},
            "source": {"class_": "File", "property_": "externalId"},
        },
        {
            "destination": {"class_": "CogniteFile", "property_": "name"},
            "source": {"class_": "File", "property_": "name"},
        },
        {
            "destination": {"class_": "CogniteFile", "property_": "directory"},
            "source": {"class_": "File", "property_": "directory"},
        },
        {
            "destination": {"class_": "CogniteSourceSystem", "property_": "name"},
            "source": {"class_": "File", "property_": "source"},
        },
        {
            "destination": {"class_": "CogniteFile", "property_": "mimeType"},
            "source": {"class_": "File", "property_": "mimeType"},
        },
        {
            "destination": {"class_": "CogniteFile", "property_": "assets"},
            "source": {"class_": "File", "property_": "assetIds"},
        },
        {
            "destination": {"class_": "CogniteFile", "property_": "sourceCreatedTime"},
            "source": {"class_": "File", "property_": "sourceCreatedTime"},
        },
        {
            "destination": {"class_": "CogniteFile", "property_": "sourceUpdatedTime"},
            "source": {"class_": "File", "property_": "sourceModifiedTime"},
        },
        {
            "destination": {"class_": "CogniteTimeSeries", "property_": "externalId"},
            "source": {"class_": "TimeSeries", "property_": "externalId"},
        },
        {
            "destination": {"class_": "CogniteTimeSeries", "property_": "name"},
            "source": {"class_": "TimeSeries", "property_": "name"},
        },
        {
            "destination": {"class_": "CogniteTimeSeries", "property_": "type"},
            "source": {"class_": "TimeSeries", "property_": "isString"},
        },
        {
            "destination": {"class_": "CogniteTimeSeries", "property_": "sourceUnit"},
            "source": {"class_": "TimeSeries", "property_": "unit"},
        },
        {
            "destination": {"class_": "CogniteTimeSeries", "property_": "unit"},
            "source": {"class_": "TimeSeries", "property_": "unitExternalId"},
        },
        {
            "destination": {"class_": "CogniteTimeSeries", "property_": "assets"},
            "source": {"class_": "TimeSeries", "property_": "assetId"},
        },
        {
            "destination": {"class_": "CogniteTimeSeries", "property_": "isStep"},
            "source": {"class_": "TimeSeries", "property_": "isStep"},
        },
        {
            "destination": {"class_": "CogniteTimeSeries", "property_": "description"},
            "source": {"class_": "TimeSeries", "property_": "description"},
        },
    ],
}
