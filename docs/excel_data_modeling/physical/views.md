# View

## Filter
Filters are used to specify which nodes or edges should be returned when querying a view. We recommend having a
unique container for each view, and use the default filter set by the API.

**NEAT** physical data model are one-to-one with the CDF API specification for creating Data Models.
Currently we are not doing any deep validation of the filters except for basic syntax checking.
Therefore, use the filters with caution. A filter is set by writing raw JSON strings in the `Filter` column, e.g.:

| View              | Implements          | Filter                                                                                                                        |
|-------------------|---------------------|-------------------------------------------------------------------------------------------------------------------------------|
| Cognite360ImageStation | CogniteDescribable | {"and": [{"hasData": [{"type": "container", "space": "cdf_cdm_3d", "externalId": "Cognite3DGroup"}]}, {"equals": {"property": ["cdf_cdm_3d", "Cognite3DGroup", "groupType"], "value": "Station360"}}]}
|



BEWARE to properly form the JSON string, as it is easy to make mistakes. The JSON string must be a valid JSON object!