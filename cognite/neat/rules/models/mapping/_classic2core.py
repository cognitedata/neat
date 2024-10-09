from ._base import RuleMapping


def create_classic_to_core_mapping() -> RuleMapping:
    return RuleMapping.model_validate(_CLASSIC_TO_CORE)


_CLASSIC_TO_CORE = {
    "classes": [
        {"destination": {"Class": "core:CogniteAsset"}, "source": {"Class": "classic:Asset"}},
        {"destination": {"Class": "core:DataProduct"}, "source": {"Class": "classic:DataSet"}},
        {"destination": {"Class": "core:CogniteActivity"}, "source": {"Class": "classic:Event"}},
        {"destination": {"Class": "core:CogniteFile"}, "source": {"Class": "classic:File"}},
        {"destination": {"Class": "core:CogniteTimeSeries"}, "source": {"Class": "classic:TimeSeries"}},
    ],
    "properties": [
        {
            "destination": {"Class": "core:CogniteAsset", "Property": "externalId"},
            "source": {"Class": "classic:Asset", "Property": "externalId"},
        },
        {
            "destination": {"Class": "core:CogniteAsset", "Property": "name"},
            "source": {"Class": "classic:Asset", "Property": "name"},
        },
        {
            "destination": {"Class": "core:CogniteAsset", "Property": "parent"},
            "source": {"Class": "classic:Asset", "Property": "parentId"},
        },
        {
            "destination": {"Class": "core:CogniteAsset", "Property": "description"},
            "source": {"Class": "classic:Asset", "Property": "description"},
        },
        {
            "destination": {"Class": "core:CogniteSourceSystem", "Property": "name"},
            "source": {"Class": "classic:Asset", "Property": "source"},
        },
        {
            "destination": {"Class": "core:CogniteAsset", "Property": "tag"},
            "source": {"Class": "classic:Asset", "Property": "labels"},
        },
        {
            "destination": {"Class": "core:DataProduct", "Property": "externalId"},
            "source": {"Class": "classic:DataSet", "Property": "externalId"},
        },
        {
            "destination": {"Class": "core:DataProduct", "Property": "name"},
            "source": {"Class": "classic:DataSet", "Property": "name"},
        },
        {
            "destination": {"Class": "core:DataProduct", "Property": "description"},
            "source": {"Class": "classic:DataSet", "Property": "description"},
        },
        {
            "destination": {"Class": "core:DataProduct", "Property": "metadata"},
            "source": {"Class": "classic:DataSet", "Property": "metadata"},
        },
        {
            "destination": {"Class": "core:DataProduct", "Property": "writeProtected"},
            "source": {"Class": "classic:DataSet", "Property": "writeProtected"},
        },
        {
            "destination": {"Class": "core:CogniteActivity", "Property": "externalId"},
            "source": {"Class": "classic:Event", "Property": "externalId"},
        },
        {
            "destination": {"Class": "core:CogniteSchedulable", "Property": "startTime"},
            "source": {"Class": "classic:Event", "Property": "startTime"},
        },
        {
            "destination": {"Class": "core:CogniteSchedulable", "Property": "endTime"},
            "source": {"Class": "classic:Event", "Property": "endTime"},
        },
        {
            "destination": {"Class": "core:CogniteActivity", "Property": "description"},
            "source": {"Class": "classic:Event", "Property": "description"},
        },
        {
            "destination": {"Class": "core:CogniteActivity", "Property": "assets"},
            "source": {"Class": "classic:Event", "Property": "assetIds"},
        },
        {
            "destination": {"Class": "core:CogniteSourceSystem", "Property": "name"},
            "source": {"Class": "classic:Event", "Property": "source"},
        },
        {
            "destination": {"Class": "core:CogniteFile", "Property": "externalId"},
            "source": {"Class": "classic:File", "Property": "externalId"},
        },
        {
            "destination": {"Class": "core:CogniteFile", "Property": "name"},
            "source": {"Class": "classic:File", "Property": "name"},
        },
        {
            "destination": {"Class": "core:CogniteFile", "Property": "directory"},
            "source": {"Class": "classic:File", "Property": "directory"},
        },
        {
            "destination": {"Class": "core:CogniteSourceSystem", "Property": "name"},
            "source": {"Class": "classic:File", "Property": "source"},
        },
        {
            "destination": {"Class": "core:CogniteFile", "Property": "mimeType"},
            "source": {"Class": "classic:File", "Property": "mimeType"},
        },
        {
            "destination": {"Class": "core:CogniteFile", "Property": "assets"},
            "source": {"Class": "classic:File", "Property": "assetIds"},
        },
        {
            "destination": {"Class": "core:CogniteFile", "Property": "sourceCreatedTime"},
            "source": {"Class": "classic:File", "Property": "sourceCreatedTime"},
        },
        {
            "destination": {"Class": "core:CogniteFile", "Property": "sourceUpdatedTime"},
            "source": {"Class": "classic:File", "Property": "sourceModifiedTime"},
        },
        {
            "destination": {"Class": "core:CogniteTimeSeries", "Property": "externalId"},
            "source": {"Class": "classic:TimeSeries", "Property": "externalId"},
        },
        {
            "destination": {"Class": "core:CogniteTimeSeries", "Property": "name"},
            "source": {"Class": "classic:TimeSeries", "Property": "name"},
        },
        {
            "destination": {"Class": "core:CogniteTimeSeries", "Property": "type"},
            "source": {"Class": "classic:TimeSeries", "Property": "isString"},
        },
        {
            "destination": {"Class": "core:CogniteTimeSeries", "Property": "sourceUnit"},
            "source": {"Class": "classic:TimeSeries", "Property": "unit"},
        },
        {
            "destination": {"Class": "core:CogniteTimeSeries", "Property": "unit"},
            "source": {"Class": "classic:TimeSeries", "Property": "unitExternalId"},
        },
        {
            "destination": {"Class": "core:CogniteTimeSeries", "Property": "assets"},
            "source": {"Class": "classic:TimeSeries", "Property": "assetId"},
        },
        {
            "destination": {"Class": "core:CogniteTimeSeries", "Property": "isStep"},
            "source": {"Class": "classic:TimeSeries", "Property": "isStep"},
        },
        {
            "destination": {"Class": "core:CogniteTimeSeries", "Property": "description"},
            "source": {"Class": "classic:TimeSeries", "Property": "description"},
        },
    ],
}
