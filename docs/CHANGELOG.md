# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Changes are grouped as follows:

- `Added` for new features.
- `Changed` for changes in existing functionality.
- `Deprecated` for soon-to-be removed features.
- `Improved` for transparent changes, e.`g. better performance.
- `Removed` for now removed features.
- `Fixed` for any bug fixes.
- `Security` in case of vulnerabilities.
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

- Fixed error propogation from sub workflows to main workflow. Now if sub workflow fails, main workflow will fail as well.
- Small UI improvments.

## [0.13.1] - 11-06-23

### Added

- Configurable cdf client timeout and max workers size. See [getting started](/getting-started.md) for details.
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
- Improved config.yaml handling . Now if the file is not found, NEAT will create a new one with default values.

## [0.7.1] - 28-03-23

- Fixed issue with relationship diffing which caused diffing to not behave as expected
- Fixed issue with end_time of resurrected resources which was not property set to None
- Moved from using python dictionaries to using data frame as prime storage of relationships
- Better handling of updated relationships via RelationshipUpdate class

## [0.1.0] - 23-03-23

This changelog was introduced to the package.
