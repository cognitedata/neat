# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Changes are grouped as follows:

- `Added` for new features.
- `Changed` for changes in existing functionality.
- `Deprecated` for soon-to-be removed features.
- `Improved` for transparent changes, e.g. better performance.
- `Removed` for now removed features.
- `Fixed` for any bug fixes.
- `Security` in case of vulnerabilities.

## [0.68.4] - 21-03-24
### Improved
- `ExcelExporter` and `YAMLExporter` now skips the default spaces and version when exporting rules.

## [0.68.3] - 20-03-24
### Fixed
- returned functionality that was accidentally removed in 0.68.1 release.
- removed excessive logging for workflow state endpoint.
- gracefull handling of transformations that do not return any data.

## [0.68.2] - 21-03-24
### Added

* Support for exporting DMS schema, in `DMSExporter`, to directory instead of just `.zip`.]

## [0.68.1] - 19-03-24
### Changed

* Default workflow `Export DMS` now also exports transformations and raw tables.

## [0.68.0] - 19-03-24
Multiple fixes and features for the upcoming v1.0.0 release.
## Added
* YAML (json) Exporter and Importer
* DMS Rules:
  * Support for revers direct relations
  * Views have support for InModel option to exclude views from the data model.
  * Views have support for Filters (`hasData` and `nodeType`)
  * List of direct relations are converted to edges.
* Robustify reading of rules, all extra whitespaces are now stripped.
* Option for exporting Transformations + Raw Tabels based on DMS rules.
* Workflows:
  * `ValidateWorklow` can also be used to covert rules.
  * Visualization of data model workflows.


## Fixed
* Bugs in the `ExcelImporter`:
  * It was not releasing the Excel file after reading it.
  * Warnings were not captured.
  * Pydantic errors were not captured.

## [0.67.5] - 14-03-24
## Fixed
* Replaced obsolete `dataModelID` Metadata filed to `external_id`


## [0.67.4] - 14-03-24
## Fixed
* Upgrade to `cognite-sdk` `7.28.2` which has fixed bug for retrieving more than 100 data models, containers,
  views, and spaces.

## [0.67.3] - 13-03-24
## Fixed
* `ExcelImporter` now returns rules for the correct role type based on the input.

## [0.67.2] - 13-03-24
## Added
- Standardization of casing in DMS exporter
- In DTDL importer infer data model name and space.
- Visualization of data model in UI through the new workflow `Visualize Data Model`
## Changed
- Deprecation of steps based on the single rule sheet, in favor of role-based rules.


## [0.67.1] - 12-03-24
## Changed
- Addeded configuraion that controls behaviour of embedded transformation logic in GenerateNodesAndEdgesFromGraph. Now user can disable default transfomation logic (before it was always on) , it is useful when transformation is done in dedicated transformation step.

## [0.67.0] - 07-03-24
## Fixed
- Fixed issue with prefixes not being updated during GraphStore (oxi) reinitialization
- Fixed graph store reset issue for JSON loader
- Small UI adjustments

## Added
- Added rules browser to the UI. Now user can browse all rules in UI from local store .
- Added configurable HTTP headers for `DownloadDataFromRestApiToFile` step. The feature is useful when the API requires specific headers to be set (has been requested by Cognite customer).

## [0.66.1] - 06-03-24
## Fixed
- `Import DMS` fails for data models without description. This is now fixed.

## [0.66.0] - 06-03-24
## Added
- Multiple experimental workflows `Export DMS`, `Import DMS`, `Validate Solution Model`, and `Validate Rules`

## [0.65.0] - 01-03-24
## Added
- Added support for scheduling on given weekdays for time trigger

## [0.64.0] - 21-03-24
## Added
- Added functionality to import and export global configuration file to and from CDF
- Added "latest" flag for workflows in CDF and spreadsheets.
- Added well formatted context viewer

## Changed
- Changed the way how workflows and rules loaded to CDF. Labels has been removed and replaced with additional metadata.

## Improved
- Improved UI around files upload and download. Improved File Uploader step.

## [0.63.0] - 20-02-24

## Added
- Added option to map edges as temporal solution prior shifting to Rules profiling


## [0.62.1] - 14-02-24

## Fixed
- Issue of `DeleteDMSSchemaComponents` deleting components in all spaces
- Issue of `ExportRulesToOntology` and `ExportRulesToSHACL` not creating missing folder

## [0.62.0] - 08-02-24

## Added
- Added `export_rules_to_ontology` workflow
- `LoadGraphToRdfFile` step to load graph to rdf file

## Fixed
- Issue of resetting graph for `MemoryStore` when loading graph from file
- Issue of not respecting add_base_prefix == False


## [0.61.0] - 06-02-24

## Added
- Ability to upload of all spaces components or only ones that are in space defined by `Rules.metadata.space`
- Ability to remove of all spaces components or only ones that are in space defined by `Rules.metadata.space`

## Improved
- DMS Schema components upload report add to step `ExportDMSSchemaComponentsToCDF`
- DMS Schema components removal report add to step `DeleteDMSSchemaComponents`
- Handling of multiple steps

## Removed
- `DataModelFromRulesToSourceGraph` it is confusing step and needs more work to be useful
- Workflows:
  - `json_to_data_model_rules`
  - `sheet2cdf`
  - `skos2cdf`

## Changed
- Renamed steps:
  - `LoadTransformationRules` to `ImportExcelToRules`
  - `InstancesFromRdfFileToSourceGraph` to `ExtractGraphFromRdfFile`
  - `InstancesFromRulesToSolutionGraph` to `ExtractGraphFromRulesInstanceSheet`
  - `GraphCapturingSheetToGraph` to `ExtractGraphFromGraphCapturingSheet`
  - `GenerateMockGraph` to `ExtractGraphFromMockGraph`
  - `InstancesFromJsonToGraph` to `ExtractGraphFromJsonFile`
  - `InstancesFromAvevaPiAF` to `ExtractGraphFromAvevaPiAssetFramework`
  - `DexpiToGraph` to `ExtractGraphFromDexpiFile`
  - `GenerateCDFAssetsFromGraph` to `GenerateAssetsFromGraph`
  - `GenerateCDFRelationshipsFromGraph` to `GenerateRelationshipsFromGraph`
  - `GenerateCDFNodesAndEdgesFromGraph` to `GenerateNodesAndEdgesFromGraph`
  - `UploadCDFAssets` to `LoadAssetsToCDF`
  - `UploadCDFRelationships` to `LoadRelationshipsToCDF`
  - `UploadCDFNodes` to `LoadNodesToCDF`
  - `UploadCDFEdges` to `LoadEdgesToCDF`
  - `CreateCDFLabels` to `LoadLabelsToCDF`
  - `OpenApiToRules` to `ImportOpenApiToRules
  - `ArbitraryJsonYamlToRules` to `ImportArbitraryJsonYamlToRules`
  - `GraphToRules` to `ImportGraphToRules`
  - `OntologyToRules` to `ImportOntologyToRules`
  - `GraphQLSchemaFromRules` to `ExportGraphQLSchemaFromRules`
  - `OntologyFromRules` to `ExportOntologyFromRules`
  - `SHACLFromRules` to `ExportSHACLFromRules`
  - `GraphCaptureSpreadsheetFromRules` to `ExportRulesToGraphCapturingSheet`
  - `ExcelFromRules` to `ExportRulesToExcel`
- Renamed workflows:
  - `graph_to_asset_hierarchy` to `extract_rdf_graph_generate_assets`
  - `dexpi2graph` to `extract_dexpi_graph_and_export_rules`
  - `ontology2data_model` to `import_ontology`

- **Note** this is a breaking change, but since we are on 0. version, we can do this.


## [0.60.0] - 30-01-24

## Added

- Configuration for which DMS schema components are to be uploaded to CDF
- Configuration for which DMS schema components are to be removed to CDF
- Configuration how to handle existing CDF schema components during upload

## Changed
- Renamed `UploadDMSDataModel` to `ExportDMSSchemaComponentsToCDF` step. **Note** this is a breaking change, but
  since we are on 0. version, we can do this.
- Renamed `DeleteDMSDataModel` to `DeleteDMSSchemaComponents` step. **Note** this is a breaking change, but
  since we are on 0. version, we can do this.
- Renamed `ExportDMSDataModel` to `ExportDMSSchemaComponentsToYAML` step. **Note** this is a breaking change, but
  since we are on 0. version, we can do this.
- Renamed `DataModel` class to `DMSSchemaComponents` to better reflect the content of the class. **Note** this is a breaking change, but
  since we are on 0. version, we can do this.
- Step that waits for human approval timeout set to 1 day

## [0.59.1] - 29-01-24

## Added

- Added pre-cleaning of spaces prior validation

## Fixed

- Fixed restrictive which did not allow multiple occurrence of [.-_]


## [0.59.0] - 24-01-24

## Added

- Added `ExportDMSDataModel` to dump data model (views) and containers as YAML

## Improved

- `DMSDataModelFromRules` is now extended such that one can update space/external_id/version of data model


## [0.58.0] - 20-01-24

## Changed

- `cognite.neat.graph.loaders.rdf_to_dms.rdf2nodes_and_edges` has been replaced by `cognite.neat.graph.loaders.DMSLoader`.
- Upgrade `cognite-sdk` to `v7`, thus now neat requires `cognite-sdk>=7.13.8`.

## Added

- Introduced an interface for `cognite.neat.graph.loaders` and implemented it for DMS.

## [0.57.0] - 11-01-24

## Improved

- Improved `GraphCapturingSheet` extractor allowing additional configuration and usage of external ids for properties and classes


## [0.56.1] - 10-01-24

## Fixed

- Add `alpha` tag to DEXPI step



## [0.56.0] - 09-01-24

## Added

- Added DEXPI example from DISC project (kindly provided by Jan Eivind Danielsen)


## [0.55.0] - 09-01-24

## Added

- Support for knowledge graph extraction from `DEXPI` P&ID provided as `XML`
- Added `DexpiToGraph` to step library


## [0.54.0] - 04-01-24

## Added
- Reset graph option for GraphDBStore

## Changed
- `cognite.neat.stores` module. This now only has four classes: `NeatGraphStoreBase`, `MemoryStore`, `OxiGraphStore`,
  and `GraphDBStore` as well as the constants `STORE_BY_TYPE` and `AVAILABLE_STORES`. All functions, enums, and previous
  classes are removed. Note `NeatGraphStoreBase` is a rename from `NeatGraphStore` and is now an abstract class.

## [0.53.0] - 03-01-24

## Improved

- Speed of nodes & edges generation
- Multi namespace support for nodes & edges generation (see [feature request](https://github.com/cognitedata/neat/issues/171))

## Changed
- `cognite.neat.extractors` module. This now only has three classes: `BaseExtractor`, `MockGraphGenerator`, `GraphCapturingSheet`.
   all the functions that were in the module is replaced with the above classes. The exception is the the function
   `rdf_file_to_graph` which is moved to `cognite.neat.graph.stores`.

## [0.52.0] - 22-12-23

## Added

- Advance data modeling support introduced
- Multi space containers support introduced


## [0.51.0] - 05-12-23

## Improved

- Turning `ParentClass` string into `Entity`
- Added new fields to Class and Property as last step to enable advance data modeling

## Removed

- Removed two validators from Rules which would otherwise block advance data modeling, specifically referring to Views and/or Containers in different spaces


## [0.50.0] - 15-12-23

## Fixed

- Fixed bug in GenerateCDFAssetsFromGraph class for assets_cleanup_type "orphans"/"full" where not all orphans assets were removed. No all asset under a created orphan parent asset are removed.


## [0.49.0] - 05-12-23

## Deprecated

- `data_set_id`, `cdfSpaceName`, `externalIdPrefix` in `Metadata` sheet has been removed

## Improved

- `Metadata` sheet now contains only two mandatory fields, namely: `prefix`, `version`, other fields are optional or generated automatically
- Generation of `Labels`, `Asset` and `Relationship` requires explicit configuration of `data_set_id` and external id prefixes, enabling reuse of same rules for multiple data sets

## [0.48.0] - 05-12-23

## Added

- Value types are now resolved as `ValueType` object instances

## [0.47.0] - 01-12-23

## Deprecated

- `type_mapping` in `rules` replaced by `value_types`

## [0.46.0] - 30-11-23

## Improved

- Improved `Triple` pydantic class to be used across the package as prep for advanced data modeling
- Improved `Entity` pydantic class to be used across the package as prep for advanced data modeling
- Moved all base regex patterns to `neat.rules.models._base`
- Reduced and cleaned up `neat.rules.models.rdfpath`

## Added

- `neat.rules.value_types` to create default ValueType class to be used to improve `Rules`

## [0.45.0] - 24-11-23

## Improved

- Validators skipping now made through two decorators `skip_field_validator` and `skip_model_validator`
- Small fixes in `cognite.neat.rules.models.rules`
- Allow single character properties/classes in `rdfpath`

## [0.44.0] - 24-11-23

## Fixed

- Fixed bug in GenerateCDFAssetsFromGraph class for assets_cleanup_type "orphans" where children of orphans assets were not removed. No all asset under an orphan parent asset are removed.

## [0.43.0] - 23-11-23

## Added

- All neat specific validators for `Rules` can be now skipped by specifying them in `validators_to_skip`, alternatively one can set `validators_to_skip=["all"]` to skip all validators.

## Fixed

- Single character properties/classes are now allowed in `rdfpath`

## [0.42.4] - 22-11-23

## Fixed

- Fixed missing oxi graph in docker

## [0.42.3] - 22-11-23

## Fixed

- Fixed max character length for `Description` to 1024 characters.

## [0.42.2] - 22-11-23

## Fixed

- Fixed absolute path in `neat` steps.

## [0.42.1] - 22-11-23

## Fixed

- `DownloadFileFromCDF` now can autocreate missing folders
- `DownloadDataFromRestApiToFile` now can autocreate missing folders

## [0.42.0] - 22-11-23

## Improved

- `OWLImporter` improved to handle exceptions often found in OWL files

## Added

- `OWLImporter` supports conversion of information to data model through flag `make_compliant`

## Fixed

- Description of properties, classes and data model updated to allow for 1028 characters

## [0.41.6] - 20-11-23

## Changed

- cdf space name regex

## [0.41.5] - 20-11-23

## Changed

- version regex

## [0.41.4] - 18-11-23

## Changed

- Python depedency `openpyxl` made mandatory

## [0.41.3] - 18-11-23

## Changed

- Python depedency `pyoxigraph` made optional

## [0.41.2] - 17-11-23

## Changed

- Python depedency from `python = ">=3.10,<3.13"` to `python = "^3.10"`

## [0.41.1] - 14-11-23

## Fixed

- Fixed `DMSImporter` to properly set `version` and `cdfSpaceName` when using single View as input.
- Fixed `rules_to_pydantic_models` to skip creating `edges-one-to-one` if `externalID` is missing

## [0.41.0] - 14-11-23

## Changed

- Renamed `JSONImporter`, `YAMLImporter`, `DictImporter` to `ArbitraryJSONmporter`, `ArbitraryYAMLImporter`, `ArbitraryDictImporter` to
  reflect that these importers infer the data model from raw input data, and are not reading a serialized file.

## Added

- Support for configuring the direction for child-parent relationship in `ArbitraryJSONmporter`, `ArbitraryYAMLImporter`, `ArbitraryDictImporter`.
- Support for `datetime` in `ArbitraryJSONmporter`, `ArbitraryYAMLImporter`, `ArbitraryDictImporter`.

## Fixed

- `DMSExporter` does not write one-to-many edges to containers any more.
- In the importers `ArbitraryJSONmporter`, `ArbitraryYAMLImporter`, `ArbitraryDictImporter` the `max_count` were not set leading all triples to
  be a one-to-many relationship. Now, only data which are of type `list` skips the `max_count` all other set it to 1.

## [0.40.2] - 14-11-23

## Fixed

- Set lower bound of `cognite-sdk` to `6.39.2` as it is required due to a bug in earlier SDK versions.

## Improved

- Improved Nodes and Edges validation and data validation reporting in rdf2nodes_and_edges and GenerateCDFNodesAndEdgesFromGraph steps.

## [0.40.1] - 08-11-23

## Changed

- The `DMSExporter` is now configurable with `datamodel_id`. The `DMSImporter` also accepts a data model as input.

## [0.40.0] - 08-11-23

## Changed

- The interface for `cognite.neat.rules.exporters`. Now, they have the following methods `.export()`, `.export_to_file()`,
  `.from_rule()`.

## [0.39.1] - 08-11-23

## Fixed

- Changed `attributes`, `edges_one_to_one`, `edges_one_to_many` instance to class property methods

## [0.39.0] - 03-11-23

## Fixed

- Not allowing DMS non-compliant Rules to be turned into pydantic models

## Added

- class property methods to the generated pydantic models accessing descriptions and names of models and fields
- controlling whether `neat` specific fields should be added or not to pydantic models using arg `add_extra_fields`
- `OntologyToRules` step added to the step library

## Improves

- Documentation of `rules_to_pydantic_models`

## [0.38.3] - 03-11-23

## Fixed

- Fixed CDF database configuration for rawlookup rule in TransformSourceToSolutionGraph . https://github.com/cognitedata/neat/issues/157

## [0.38.2] - 03-11-23

## Fixed

- Added type mapping for data type Date

## [0.38.1] - 01-11-23

## Fixed

- Proper min_count for `DMSImporter` base on CDF `View` implementation

## [0.38.0] - 31-10-23

## Added

- Ability to partially validate Rules
- Description and name of fields added to rules generated pydantic models

## Improved

- Improved naming of internal variables in `cognite/neat/rules/exporter/rules2pydantic_models.py`

## [0.37.0] - 31-10-23

## Added

- Configurable assets cleanup in GenerateCDFAssetsFromGraph step. Now user can specify if he/she wants to delete all ophan or circular assets or keep them.

### Fixed

- https://github.com/cognitedata/neat/issues/146
- https://github.com/cognitedata/neat/issues/139

## [0.36.0] - 30-10-23

### Added

- Added `DMSImporter`
-

## [0.35.0] - 27-10-23

### Improved

- Improved stability and resource usage of Oxigraph when working with large graphs.

### Added

- Added `InstancesFromAvevaPiAF` step.

### Fixed

- UI bug fixes and improvements.

## [0.34.0] - 27-10-23

### Improved

- Bug fix: Removed condition not allowing an asset to change its parent asset.

## [0.33.0] - 22-10-23

### Improved

- Implementation of class prefix to external ids for edges

## [0.32.0] - 22-10-23

### Improved

- Refactor importers
- Simplified data modeling flow by introducing RawRules as a first class citizen
- Fix small bugs
- Initiated refactor of exporters

## [0.31.0] - 18-10-23

### Added

- Importer `GraphImporter`

### Improved

- Base importer with generic, yet configurable, exceptions

## [0.30.0] - 11-10-23

### Added

- Three importers `JSONImporter`, `YAMLImporter`, and `DictImporter`.

## [0.29.0] - 07-10-23

### Changed

- The importer `owl2excel` is written as a class `OWLImporter`. **Note** this is a breaking change, but
  since we are on 0. version, we can do this.

## [0.28.0] - 07-10-23

### Added

- Classes for extractors `MockGraphGenerator` and `GraphCapturingSheet` available at `cognite.neat.graph.extractors`.

## [0.27.1] - 07-10-23

### Improved

- Introduced container classes for `Classes` and `Properties` in `TransformationRules`. Implemented `.to_pandas()`
  methods for both classes.

## [0.27.0] - 07-10-23

### Added

- `neat` support Python `3.10`.

## [0.26.1] - 05-10-23

### Fixed

- Small fixes related to steps compatibility with mypy.
- Fixed UI crash in case if workflow state cannot be loaded.
- Fixed step loader from data_folder/steps path.

### Added

- Workflow id and run id are now available as step object variables.

## [0.26.0] - 04-10-23

### Added

- Added rules2excel rules exporter. Now users can export rules from TransformationRules object to excel file.
- Added rules generator step from arbitrary object (must be in json or yaml formats)
- Added eperimental rules parser from OpenApi/Swagger specification. Rules generates based on schema part of OpenApi specification.
- Added version , source and docs_urs metadata to Steps class.

## [0.25.9] - 30-09-23

### Fixed

- Loading `neat` from environment variables, the variable `NEAT_LOAD_EXAMPLES` would always return `true`
  even if it was set to `false`. This is now fixed.

## [0.25.8] - 20-09-23

### Improved

- Many UI improvements and bug fixes.
- Improved data exploration capabilities.

### Added

- Added universal JSON to Graph extractor step.

## [0.25.7] - 14-09-23

### Added

- Drop down menu for selection of property which hold value for nodes in Data Explorer

## [0.25.6] - 12-09-23

### Fixed

- Fixed Nodes and Edges step
- Fixed issues with regex

### Added

- Mock Graph Generation Step
- Regex patterns from CDF API documentation

## [0.25.5] - 5-09-23

### Added

- Support for upload of various RDF formats to `NeatGraph` store

## [0.25.4] - 5-09-23

### Fixed

- Fixed issue when columns names are non-string
- Fixed missing start_time in relationships
- Fixed upload_nodes/edges
- Fixed DMS upload step

### Added

- Handling of edge cases when creating Assets in which name was pushed to be None even though there is alt property
- Notebook 5 with walk through about fDM, nodes and edges

## [0.25.3] - 4-09-23

### Fixed

- Fixed Github rules loader.

### Changed

- Github rules loader now split into Github downloader step and RulesLoader.

### Added

- Added Input/Output steps for downloading and uploading rules from/to Github and from/to CDF files.

## [0.25.2] - 1-09-23

### Fixed

- Multiple UI usability improvements and bug fixes.

## [0.25.1] - 31-08-23

### Fixed

- Fixed issues with regex validations for entity ids

## [0.25.0] - 30-08-23

### Changed

- New way of configuring workflows steps . Now steps are configured individually and not as a part of workflow manifest.
- Added access_token autentication for Cognite client. If client_id is not set in config.yaml, NEAT will use client_secret as access_token.
- Multiple UI usability improvements and bug fixes.

### Added

- Added SimpleContextualization step . The step can be used to create links between nodes in a graph either by using regex or exact match between source and target properties.
- Added single store configuration step. Now solution and graph stores can be configured individually.

## [0.24.2] - 29-08-23

### Added

- Multi parent classes are now allowed
- Validation of parent classes ids against class id regex
- New Exception in case of ill-formed parent class ids

### Fixed

- Bug raising when generating Ontology triples in case when there are multi parent classes

## [0.24.1] - 29-08-23

### Added

- Docstring to `cognite.neat.rules.exceptions` and `cognite.neat.graph.exceptions`
- URL to exception definition added to exception message
- Rendering of exceptions in `docs` (mkdocs)

### Fixed

- `fix_namespace_ending` was returning `str` instead of `Namespace` causing issues

### Improved

- Split docs config of importers to importers and parsers to avoid confusion

## [0.24.0] - 24-08-23

### Added

- Generation of DM instances
- `DMSDataModelFromRules`, `GenerateCDFNodesAndEdgesFromGraph`, `UploadCDFNodes` and `UploadCDFEdges` added to step libary

### Improved

- Handling of generation of pydantic model instances in case of incomplete graph instances

## [0.22.0] - 22-08-23

### Changed

- Re-org and re-name step library
- Update workflows according to new step library org

### Added

- `OntologyFromRules` step to step library
- `SHACLFromRules` step to step library
- `DownloadTransformationRulesFromGitHub` to step library

### Improved

- `data_model_generation` workflow has been extended to produce ontological and shape constraints representation
- input parameters description for workflow steps in step library

## [0.21.2] - 18-08-23

### Changed

- `cognite.neat.rules.exceptions` warnings and errors names changed to human-readable form

## [0.21.1] - 18-08-23

### Changed

- `rules2dms` is updated to query for specific version of views

## [0.21.0] - 17-08-23

### Changed

- BIG workflow refactoring. New workflow concept is more modular and easier to extend.
- Steps are defined as independent components with well defined inputs and output data contracts/types and configurations.
- Steps are now reusable and scoped to 3 categories: `global`, `project` and `workflow`. Global steps are available to all workflows and maintained by NEAT project, `project`scoped steps are available to all workflows in a project and `workflow` scoped steps defined and available only to a specific workflow.
- Workflows are now defined as a composition of steps via manifest file , pytyhon file is no longer needed. Workflow Base class inheritance is still possible but not recomended and reserved for very advanced use cases.

### Removed

- Removed `base`and `default` workflows.

### Added

- Workflows can be added via UI.

### Improved

- Improved drop operations for NeatGraph store.

## [0.20.0] - 08-08-23

### Added

- Generation of data model in DMS through `sdk` interaction with DMS endpoint

## [0.19.0] - 08-08-23

### Added

- Generation of in-memory pydantic models based on class/property definitions in `TransformationRules`
- Generation of `CONSTRUCT` query which provides "views" into source graph and in most cases alleviate the need of creating solution graph

## [0.18.3] - 01-08-23

### Changed

- First pass of refactoring / reorg of `app/api` package

### Added

- With exception of `get-nodes-and-edges` route and routes that need CDF all other are now tested

### Removed

- Running tests only on `graph_to_asset_hierarchy`, `sheet2cdf` is commented out

## [0.18.2] - 26-07-23

### Changed

- First pass of refactoring / reorg of `workflows` package
- Removed some of examples data from `neat` and place them under tests

## [0.18.1] - 25-07-23

### Changed

- Structure of `neat` package
- Structure of `neat` tests to reflect package structure
- Renamed rules loaders into readers
- Merged rules readers and parsers into parser

## [0.18.0] - 25-07-23

### Changed

- Structure of `neat` package.

## [0.17.4] - 24-07-23

### Added

- Generation of ontology, shape constraint objects and semantic data model out of transformation rules

## [0.17.3] - 24-07-23

### Added

- Added new composition based method of building step-components for NEAT workflows.

## [0.17.2] - 20-07-23

### Changed

- Switch to using `jinja2` template engine instead of `graphql-core` for generation of GraphQL schema

### Added

- Downloading rules from private github repository

## [0.17.1] - 19-07-23

### Changed

- Organized various methods that work with `TransformationRules` to importers/exporters and set of methods that perform rules analysis

## [0.17.0] - 16-07-23

### Changed

- Parsing of Transformation Rules from Excel files more stricter validations
- BREAKING CHANGE: Transformation Rules which contain Instances sheet now required namespace to be explicitly set in Metadata sheet !

### Added

- Dedicated module for exceptions (warnings/errors) for Transformation Rules parsing
- Ability to generate parsing report containing warnings/errors
- Conversion of OWL ontologies to Transformation Rules
- Tests for notebooks

## [0.16.0] - 10-07-23

### Changed

- The subpackage inside `cognite-neat` `core.rules` has now a defined inteface with three different load methods
  along with the data classes those load methods returns.
- Started making dependencies optional and setting up options for installing `neat` for different use cases.

## [0.15.0] - 08-07-23

### Changed

- Require `pydantic` `v2`.

## [0.14.2] - 07-07-23

### Added

- Added additional validators to comply with CDF DM
- Added new fields to handle request for having both entity ids and entity names
- Added new fields to capture necessary information to resolve sheets as (f)DM

## [0.14.1] - 30-06-23

### Fixed

- Fixed bugs in base workflows

### Improved

- Improved graph based data exploration capabilities.

## [0.14.0] - 21-06-23

### Added

- Base workflow concept. Most of common functionality is moved to base workflows. Now it is possible to create custom
  workflows by inheriting from base workflow. More infor in docs
- Added 3 main workflow start methods . More info in docs

### Fixed

- Fixed error propagation from sub workflows to main workflow. Now if sub workflow fails, main workflow will fail as well.
- Small UI improvements.

## [0.13.1] - 11-06-23

### Added

- Configurable cdf client timeout and max workers size. See [getting started](installation.md) for details.
- Additional logic for handling `CogniteReadTimeoutError` and `CogniteDuplicatedError` during retries. This is an attempt
  to handle cases when under heavy load, requests to CDF may timeout even though the requests were processed successfully
  in eventual consistancy manner.

## [0.13.0] - 11-06-23

### Added

- Configuration option for metadata keys used by neat in the `sheet2cdf` workflow.

## [0.12.10] - 11-06-23

### Improved

- `cognite-neat` package metadata.

## [0.12.9] - 11-06-23

### Fixed

- Existing CDF asset without a label caused the `sheet2cdf` workflow to fail. This is now fixed.

## [0.12.8] - 09-06-23

### Fixed

- Clean labels from assets which do not exist in CDF. This one does the cleaning correct, while `0.12.7` assumed
  the wrong internal format for asset, and thus, did not work.

## [0.12.7] - 07-06-23

### Fixed

- Handling assets in CDF with non-existing labels.

## [0.12.6] - 06-06-23

### Fixed

- Handling assets without labels in CDF.

## [0.12.5] - 04-06-23

### Added

- Automatic update (configurable) of workflow configurations (using new file name) on the rules file upload completion
- Automatic triggering (configurable) of workflow execution on rules file upload completion

## [0.12.4] - 30-05-23

### Added

- SME graph capturing workflow that make use of core method from 0.12.3
- FDM schema generation workflow that make use of core method from 0.11.2
- FDM schema generation notebook in docs
- SME graph capturing notebook in docs

### Improved

- Notebooks overall

### Fixed

- Handling of Instances sheet, issue with cell datatypes

### Changed

- Renamed `fast_graph` workflow to `graph_to_asset_hierarchy`

### Removed

- Default workflow

## [0.12.3] - 30-05-23

### Added

- Added generation of knowledge graph capturing sheet based on data model definitions in transformation rules
- Added generation of knowledge graph from graph capturing sheets

## [0.12.2] - 30-05-23

### Fixed

- Default `config.yaml` could not be reloaded.

### Improved

- The output messages for `load_transformation_rules_step` in all workflows by specifying which file is used.

## [0.12.1] - 26-05-23

### Added

- Added retry logic to asset and relationship update micro batching
- Added generic workflow steps retry logic
- Added examples of how to use update safety guards and human approval steps in workflows

### Fixed

- Fixed UI state polling bug.

## [0.12.0] - 23-05-23

### Added

- Added workflow documentation.
- Added `wait_for_event` task. This task will wait for a specific event to occur.Can be used to pause/resume workflow execution , for instance when a user needs to approve the workflow execution.
- Added metrics helper functions. These functions can be used to create metrics for the workflow.
- Added UI configuration editor. Now it supports all UI operations.
- Added workflow source code viewer.
- Added rules file download link. Now user can upload and download rules file via NEAT UI .
- Added error reporting in UI if the rules file is not valid or not present. The same for data exploration view.

### Improved

- Many UI improvements and visual regrouping of UI views.
- Improved http trigger. Now it can receive arbitrary data in json format.
- Global configurations moved to its own view.
- Steps and System components editor supports node removal.

### Changed

- Groups section was renamed to Solution/System components overview. In manifest it was renamed to `system_components`.

## [0.11.5] - 23-05-23

### Fixed

- Removed `data/config.yaml` dump. This is not used.
- If the config is not specified, the default `config.yaml` now dumps it content as yaml and not `json`.

## [0.11.4] - 22-05-23

### Added

- Reporting on categorized assets and relationships
- Safety gauge to skip assets which are changing asset hierarchy or to raise exception

## [0.11.3] - 19-05-23

### Fixed

- When running `neat` with two different datasets without an external_id prefix, the creation of an orphanage asset
  caused a DuplicationError. This is now fixed by suffixing the dataset to the orphanage asset.

## [0.11.2] - 15-05-23

### Added

- Generation of GraphQL schema from transformation rules
- Fixing names of classes/properties to be aligned to GraphQL allowed characters
- Allowing pure data modeling transformation rules, i.e. no data on mapping rules

## [0.11.1] - 08-05-23

### Fixed

- Set the license of the package in poetry build.

## [0.11.0] - 08-05-23

- Refactored application bootrap procese and core application functions aggregated into NeatApp class.
- Small bug fixes.
- Fixed global configurations via UI and API.

## [0.10.4] - 28-04-23

- Added readme to publish process on pypi.org.

## [0.10.3] - 26-04-23

- Handling edge case in graph that results in decommissioned relationships

## [0.10.2] - 23-04-23

- Fix issue with duplicated labels for relationships

## [0.10.1] - 20-04-23

- Fix for issue of creation of relationships for assets that do not exist

## [0.10.0] - 17-04-24

- Refactor `rdf_to_asset` to use micro batching
- Refactor `rdf_to_relationships` to use micro batching
- Improved logging and performance for `rdf_to_asset` and `rdf_to_relationships`
- Additional labels for relationships

## [0.9.2] - 05-04-23

- Refactor TransformationRules to entail data modeling, relationship definition, label creation methods

## [0.9.1] - 05-04-23

- Remove duplicated rules for relationships which are causing duplicated relationships
- Improve performance of relationship categorization
- Improve NeatGraphStore to better handle graph.drop() for in-memory store
- Improved current example workflows

## [0.9.0] - 03-04-23

- Created mock module
- Added generation of mock graphs based on data model provided in transformation rules
- DataModelingDefinition class extended with methods:
  - `reduce_data_model`: Reduces the data model to desired set of classes
  - `to_dataframe` : Converts DataModelingDefinition instance to a pandas dataframe for easier manipulation
  - `get_class_linkage`: gets the linkage between classes in the data model
  - `get_symmetric_pairs`: gets the symmetric pairs of classes in the data model
- Added descriptive notebook demoing the use of the mock graph generator

## [0.8.0] - 30-03-23

### Added

- Entry point for launching neat application, `neat`.

## [0.7.2] - 28-03-23

- Removed unused API methods
- Added Workflow Execution History to the UI and API (viewer only)
- Added workflow methods for reinitializing CogniteClient from within a workflow. Should be used by workflows to adress memmory leaks in the CogniteClient.
- Improved config.yaml handling. Now if the file is not found, NEAT will create a new one with default values.

## [0.7.1] - 28-03-23

- Fixed issue with relationship diffing which caused diffing to not behave as expected
- Fixed issue with end_time of resurrected resources which was not property set to None
- Moved from using python dictionaries to using data frame as prime storage of relationships
- Better handling of updated relationships via RelationshipUpdate class

## [0.7.0] - 23-03-23

This changelog was introduced to the package.
