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

## [0.12.2] - 30-05-23

### Fixed
* Default `config.yaml` could not be reloaded.

### Improved
* The output messages for `load_transformation_rules_step` in all workflows by specifying which file is used.


## [0.12.1] - 26-05-23

### Added
* Added retry logic to asset and relationship update micro batching
* Added generic workflow steps retry logic
* Added examples of how to use update safety guards and human approval steps in workflows

### Fixed
* Fixed UI state polling bug.


## [0.12.0] - 23-05-23
### Added
* Added workflow documentation.
* Added `wait_for_event` task. This task will wait for a specific event to occur.Can be used to pause/resume workflow execution , for instance when a user needs to approve the workflow execution.
* Added metrics helper functions. These functions can be used to create metrics for the workflow.
* Added UI configuration editor. Now it supports all UI operations.
* Added workflow source code viewer.
* Added rules file download link. Now user can upload and download rules file via NEAT UI .
* Added error reporting in UI if the rules file is not valid or not present. The same for data exploration view.


### Improved
* Many UI improvements and visual regrouping of UI views.
* Improved http trigger. Now it can receive arbitrary data in json format.
* Global configurations moved to its own view.
* Steps and System components editor supports node removal.


### Changed
* Groups section was renamed to Solution/System components overview. In manifest it was renamed to `system_components`.

## [0.11.5] - 23-05-23
### Fixed
* Removed `data/config.yaml` dump. This is not used.
* If the config is not specified, the default `config.yaml` now dumps it content as yaml and not `json`.

## [0.11.4] - 22-05-23
### Added
* Reporting on categorized assets and relationships
* Safety gauge to skip assets which are changing asset hierarchy or to raise exception

## [0.11.3] - 19-05-23
### Fixed
* When running `neat` with two different datasets without an external_id prefix, the creation of an orphanage asset
  caused a DuplicationError. This is now fixed by suffixing the dataset to the orphanage asset.


## [0.11.2] - 15-05-23
### Added
* Generation of GraphQL schema from transformation rules
* Fixing names of classes/properties to be aligned to GraphQL allowed characters
* Allowing pure data modeling transformation rules, i.e. no data on mapping rules

## [0.11.1] - 08-05-23

### Fixed

* Set the license of the package in poetry build.

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
- Added  Workflow Execution History to the UI and API (viewer only)
- Added  workflow methods for reinitializing CogniteClient from within a workflow. Should be used by workflows to adress memmory leaks in the CogniteClient.
- Improved config.yaml handling . Now if the file is not found, NEAT will create a new one with default values.

## [0.7.1] - 28-03-23

- Fixed issue with relationship diffing which caused diffing to not behave as expected
- Fixed issue with end_time of resurrected resources which was not property set to None
- Moved from using python dictionaries to using data frame as prime storage of relationships
- Better handling of updated relationships via RelationshipUpdate class

## [0.1.0] - 23-03-23

This changelog was introduced to the package.
