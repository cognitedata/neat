# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Changes are grouped as follows
- `Added` for new features.
- `Changed` for changes in existing functionality.
- `Deprecated` for soon-to-be removed features.
- `Improved` for transparent changes, e.g. better performance.
- `Removed` for now removed features.
- `Fixed` for any bug fixes.
- `Security` in case of vulnerabilities.

## [0.10.3] - 26-04-24
- Handling edge case in graph that results in decommissioned relationships
## [0.10.2] - 23-04-24
- Fix issue with duplicated labels for relationships

## [0.10.1] - 20-04-24
- Fix for issue of creation of relationships for assets that do not exist
## [0.10.0] - 17-04-24
- Refactor `rdf_to_asset` to use micro batching
- Refactor `rdf_to_relationships` to use micro batching
- Improved logging and performance for `rdf_to_asset` and `rdf_to_relationships`
- Additional labels for relationships

## [0.9.2] - 05-04-24
- Refactor TransformationRules to entail data modeling, relationship definition, label creation methods

## [0.9.1] - 05-04-24
- Remove duplicated rules for relationships which are causing duplicated relationships
- Improve performance of relationship categorization
- Improve NeatGraphStore to better handle graph.drop() for in-memory store
- Improved current example workflows

## [0.9.0] - 03-04-24
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
