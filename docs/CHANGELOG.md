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

## [0.97.1] - 14-11-**2024**
### Changed
- `neat.show.instances()` now only works if NeatSession storage is set to `oxigraph`
### Fixed
- `neat.prepare.data_model.to_enterprise/to_solution` was not picking up source entity
### Changed
- `lxml` is now an optional dependency for `DexpiExtractor`. This is to support running in `pyodide` environment.

## [0.97.0] - 14-11-**2024**
### Added
- Added provenance on rules in NeatSession
- Option to move connections from reference to new model in DMS rules when generating Enterprise model
- Plotting of data model provenance
- Plotting of data model implements
- Support for loading `NeatEngine`.
- Support for inspecting outcome of `neat.to.cdf.instances(...)` with `neat.inspect.outcome.instances(...)`.
- `neat.prepare.instance.make_connection_on_exact_match` added to enable adding connections
  between instances based on exact match of properties.
- Support for reading instances from csv `neat.read.csv`. Including reading csv from a public GitHub repository.

### Improved
- Case-insensitive "direct" connection type in DMS Rules
- Validation over view types for connections in DMS Rules
- Validation of reverse connection feasibility in DMS Rules

## Changed
- The `neat.infer()` now always infer integer and float as their 64-bit counterparts long and double. The motivation
  for this change is to have a more flexible data model that can handle 64-bit integers and floats.

## [0.96.6] - 08-11-**2024**
### Fixed
- `neat.verify()` no longer gives a `PrincipleMatchingSpaceAndVersionWarning` when you include views from
  the `CogniteCore` or `CogniteProcessIndustry` data models.
- In the `DMSSheet` you will now get a `RowError` if you try to set `container` or `container property` for
  an edge or reverse direct relation as these are not stored in containers.
- `neat.read.excel(...)` now correctly reads the `Enum` and `Nodes` sheets.
- In the `DMSSheet`, `reverse` relations no longer give a `RowError` if the reverse property is referencing
  a property in the reference sheets.

## [0.96.5] - 07-11-**2024**
### Fixed
- Serializing `ResourceNotDefinedError` class no longer raises a `ValueError`. This happens when a `ResourceNotDefinedError`
  is found, for example, when calling `neat.verify()`.
- Setting `neat.to.cdf.data_model(existing_handling='force)` will now correctly delete and recreate views and containers
  if they already exist in CDF.

### Improved
- When running `neat.to.cdf.data_model()` the entire response from CDF is now stored as an error message, not just the
  text.

### Added
- `neat.to.cdf.data_model()` now has a `fallback_one_by_one` parameter. If set to `True`, the views/containers will
  be created one by one, if the batch creation fails.

## [0.96.4] - 05-11-**2024**
### Fixed
- `neat.to.excel` or `neat.to.yaml` now correctly writes `ViewTypes` and `Edge` that do not have the default
  value. For example, if the `Connection` was `edge(direction=inwards)` it would not be written to the Excel or
  YAML file as `edge` as `direction=inwards` was not the default value. This is now fixed.

## [0.96.3] - 05-11-**2024**
### Added
- Introduce `neat.inspect.outcome(...)` to check the outcome of `cdf.to.data_model`.

### Fixed
- `neat.to.cdf.data_model` no longer outputs warnings when creating a new data model in CDF.

## [0.96.2] - 05-11-**2024**
### Added
- Can configure `neat.to.cdf.data_model` behavior for data model components that already exist in CDF

### Changed
- When reading a data model from CDF, `inwards` edges are now treated as an edge with direction inwards and
  not the reverse edge.

## [0.96.1] - 04-11-**2024**
### Fixed
- `naet.show` working in a pyodide environment

## [0.96.0] - 04-11-**2024**
### Improved
- Handling of CDM extension
- Switched from Cytoscape to PyVis for data model and instances visualization
### Added
- `neat.prepare.reduce` now support dropping individual views from a `Cognite` model.
- `neat.set.data_model_id` a convenience method to set the data model id in a `NeatSession`.
- `neat.version` returns the version of the `neat` package.
- `neat.prepare.to_enterprise` prepares template for creation of an enterprise model in `Cognite Data Fusion`.
- `neat.prepare.to_solution` prepares template for creation of a solution model in `Cognite Data Fusion`.


## [0.95.0] - 29-10-**2024**
### Fixed
- `NeatSession` subcommands no longer gives traceback for `NeatSessionError` exceptions, instead it
  gives a more user-friendly error message.

### Improved
- Reduced matplotlib version to 3.5.2 due to PYOD compatibility issues
- Shorter and more concise summary of the data model in NeatSession

## [0.94.0] - 29-10-**2024**
### Added
- Support for information rules and instance plotting in NeatSession
- From Source to CDF tutorial

### Improved
- Better plotting of rules for dms and information rules in NeatSession (accounts for `subClassOf` and `implements`)

## [0.93.0] - 28-10-**2024**
### Improved
- IODD extractor to also extract XML elements that should map to time series data type
- This includes extracting `VariableCollection` elements and `ProcessDataIn` elements
- Will probably need to revise how the tag/id of the time series is created
- Interfaces for InferenceImporter, IMFImporter and OWLImporter are leveraging BaseRDFImporter
- Renamed rules.examples to rules.catalog to start building catalog od data models
- Improved IMF rules that will handle IMF AttributeType onboarding
- Improved handling of unknown, multi-data, multi-objet and mixed value types in conversion from Information to DMS rules
- Reorg prefixes
- Added more detail regex testing of entities
- Transformation is now generated for every RDF based rules importer
- Improved session overview in UI

### Added
- Added `NeatSession`
- Rules exporter that produces a spreadsheet template for instance creation based on definition of classes in the rules
- Rules transformer which converts information rules entities to be DMS compliant
- Rules transformer `RuleMapping` that maps rules from one data model to another
- Graph transformer `SplitMultiValueProperty` which splits multi-value properties into separate properties with single value
- Support for `xsd:decimal` which is now mapped to `float64` in DMS rules
- Added RDF based readers for `NeatSession`
- `NeatSession.read.rdf.examples.nordic44`
- `NeatSession.show.data_model` show data model in UI

### Removed
- State on DataType stored in `_dms_loaded` attribute

### Changed
- Required `env_file_name` explicitly set in the `get_cognite_client` function. This is to avoid loading the wrong
  environment file by accident when running the function in a notebook.
- `NeatIssue` are no longer immutable. This is to comply with the expectation of Exceptions in Python.
- [BREAKING] All `NEAT` former public methods are now private. Only `NeatSession` is public.

## [0.92.3] - 17-09-24
### Fixed
- Prefixes not being imported or exported to Excel
- Trailing whitespace in Excel files causing issues with importing

## [0.92.2] - 17-09-24
### Added
- Method in `InformationAnalysis` which returns class URI based on class entity
- Method in `InformationAnalysis` which returns definition of property types for give class entity
- Allow different class entity in transformations then classes for which transformation are written(typical use case when we are renaming classes from source to target graph)

### Improved
- Handling of namespace removal in Describe query (now only values which are of URIRef type or values of properties defined as object property get get namespace removed)

### Removed
- logging from `InformationAnalysis` module

### Fixed
- NEAT can now run in a minimal environment without raising a `KeyError` when using the default
  configuration in NEAT importers.
- NEAT now strips extra whitespace in all imported strings.


## [0.92.1] - 12-09-24
### Fixed
- The version of the released docker image was not updated correctly. This is now fixed.

## [0.92.0] - 12-09-24
### Added
- `ClassicExtactor` to extract all classic resource types from CDF from a given data set or root asset.

## [0.91.0] - 11-09-24
### Added
- IODDExtractor for IO-link standard: https://io-link.com/
- The extractor will parse XML files that follow the IO-link standard for an IODD device, and create rdf triples
that will form the knowledge graph for the device.
- Improved XML utils method `get_children` to be able to extract nested children as well as direct children, and ignore
namespace prefix of each tag element if the XML contains namespaces.

## [0.90.2] - 06-09-24
### Improved
- Visualize data model chapter in Knowledge Acquisition tutorial reduce to only export of data model to ontology
- New video made for the Export Semantic Data Model chapter in Knowledge Acquisition tutorial
- Workflow `Visualize_Semantic_Data_Model` renamed to `Export_Semantic_Data_Model` and reduce to only export

### Removed
- `Visualize_Data_Model_Using_Mock_Graph` removed since UI has been reduced to only have workflow builder & executor feature

## [0.90.1] - 06-09-24
### Fixed
- Fix issue with step doing file upload leading to blank screen in UI
- Fix issue with graph store step config, leading to not being able to load triples


## [0.90.0] - 05-09-24
### Added
- `DMSExtractor` added to extract instances from CDF into NeatStore.
- `DMSLoader` now sets the node type for instances.

### Fixed
- `DMSLoader` now correctly identifies edges based on type.

## [0.89.0] - 02-09-24
### Changed
- [BREAKING CHANGE] All conversion of rules object methods, for example, `InformationRules.as_dms_rules()`, have
  been removed. Instead, use the `cognite.neat.rules.transformers` module to get an appropriate transformar
  and use the `transform` method to convert the rules object.

### Fixed
- Circular dependency

### Improved
- Handling Default for connections in DMS rules
- Updated InformationToDMS to allow for dropping of properties with unknown value types
- Handling of properties which point to non-existing nodes when doing data model inference
- Handling of conversion of Information to DMS rules which contain properties with `Unknown` value type (defaulting to connection =`direct`, with no value type)

### Added
- Support for edges with properties in DMS rules.
- Support for explicitly setting node types in DMS Rules.
- Support for units on `fload64` and `float32` in DMS Rules.
- Support for enum in DMS Rules.


## [0.88.4] - 29-08-24
### Fixed
- IMF rules importer failed to publish to CDF due to non-compliant identifiers
- Duplicate generation of properties
### Improved
- Handling of cardinality for attribute properties
- Handling of multiple predicates used for concept definitions

## [0.88.3] - 20-08-24
### Fixed
- IMF rules importer failing due to references
### Improved
- Handling of references for OWL importer
### Added
- Test for IMF importer


## [0.88.2] - 24-07-24
### Added
- IMF rules importer
### Improved
- Organization of RDF based importers


## [0.88.1] - 24-07-24
### Improved
- Implementation of oxistore is now more robust and based on existing implementation by Oxigraph developer
### Removed
- Removed unused Oxistore implementation

## [0.88.0] - 22-07-24
### Removed
- [BREAKING] Legacy neat has been removed from the codebase. This includes `legacy` module,
  steps, and UI capabilities (such as explorer and rules editor).


## [0.87.6] - 22-07-24
### Added
- Labels generation from NeatGraphStore in AssetLoader


## [0.87.5] - 22-07-24
### Added
- Relationship generation from NeatGraphStore in AssetLoader


## [0.87.4] - 22-07-24
### Added
- Support for `Immutable` in `DMSRules`

## [0.87.3] - 18-07-24
### Added
- Handling of missing parents when generating assets
- Concept of orphanage asset for assets whose parents do not exist
- Uploader to CDF for assets
### Fixed
- Issue of not loading all asset fields when calling `AssetWrite.load()` method


## [0.87.2] - 17-07-24
### Added
- Topological sorting of classes and properties in `AssetRules` to provide proper order of asset creation
- Additional validation on `AssetRules` to ensure that mapped parent properties point to class not data value type
- Additional validation on `AssetRules` to ensure that rules do not have circular decadency

## [0.87.1] - 17-07-24
### Added
- `AddSelfReferenceProperty` transformer that handles `SelfReferenceProperty` RDF path in Rules
### Improved
- Better handling of property renaming in `DESCRIBE` query, which for example allows RDF:type property to be used
- Iterating over classes which have properties defined for them instead of all classes (which causes errors)
- Renamed `AllReferences` RDF path to `SelfReferenceProperty` to better reflect its purpose
### Removed
- `AllProperties` RDF path has been removed as we no longer want support implicit properties

## [0.87.0] - 17-07-24
### Added
- `AssetLoader` added to load assets to CDF
- `get_default_prefixes` method to provide default prefixes
### Removed
- `PREFIXES` dict that was used as default prefixes in `NeatGraphStore` and `Rules`
### Improved
- `AssetRules` properties have now mandatory `implementation` field
### Fixed
- Issue of properties not being renamed in `DESCRIBE` query


## [0.86.0] - 15-07-24
### Changed
- `NeatGraphStore.read()` is now iterable utilizing `DESCRIBE` query instead of `CONSTRUCT` query.
### Improved
- Order of magnitude improved query speed of instances for downstream graph loaders


## [0.85.12] - 11-07-24
### Added
- Added handling of Json fields in DMS loader

### Fixed
- DMS related datatype .python being wrongly mapped to python types

## [0.85.11] - 10-07-24
### Added
- Method `create_reference` to `DMSRules` to add reference dms rules and do the mapping of properties
  and views to the reference model.

## [0.85.10] - 10-07-24
### Added
- Depth-based typing in `AddAssetDepth` transformer
- Graph summary repr

## [0.85.9] - 09-07-24
### Added
- Option for checking for JSON value type when inferring data model

## [0.85.8] - 09-07-24
### Added
- Option for unpacking metadata from classic CDF resources graph extractor

## [0.85.7] - 08-07-24
### Added
- Option for setting lambda function `to_type` in the `AssetExtractor`.

## [0.85.6] - 08-07-24
### Added
- Analysis for `AssetRules`

## [0.85.5] - 07-07-24
### Fixed
- Prefix collision
- Fixed issue arising when value string "null" is threated as float "null" leading to error
  in DMS Instances

### Removed
- Relation to original data model used to develop neat

## [0.85.4] - 01-07-24
### Fixed
- Another issue with docker release.

## [0.85.3] - 01-07-24
### Fixed
- Another issue with docker release.

## [0.85.2] - 01-07-24
### Fixed
- Issues with docker release.

## [0.85.1] - 01-07-24
### Fixed
- Bug when using the `get_cognite_client` function with interactive login. This is now fixed.

## [0.85.0] - 25-06-24
### Changed
- [BREAKING] Interface for `Loaders`. Instead of `.export_to_cdf` now always return `UploadResultList` and
  the `.load_into_cdf_iterable` returns an iterable of `UploadResult`. It is no longer possible to return
  just the count. This is to make the interface more notebook friendly and easier to work with.

## [0.84.1] - 26-06-24
### Added
- Conversion between information, asset and dms rules
- Added serializer for transformations (i.e. RDFPATH)
- Placeholder for AssetLoader

## [0.84.0] - 25-06-24
### Changed
- [BREAKING] Interface for `Exporters`. Instead of `.export_to_cdf` returning an iterable, it now returns a list,
  and the `.export_to_cdf_iterable` returns an iterable. In addition, these method now returns a new type of
  objects `UploadResult`. This is to make the interface more notebook friendly and easier to work with.

## [0.83.1] - 26-06-24
### Added
- Conversion between information, asset and dms rules
- Added serializer for transformations (i.e. RDFPATH)
- Placeholder for AssetLoader


## [0.83.0] - 25-06-24
### Changed
- The dependency for running the neat service `fastapi`, `uvicorn`, and `prometheus-client` have been
  made optional. This is to make it easier to use `neat` as a Python package without the need for
  these dependencies.

## [0.82.3] - 25-06-24
### Improved
- Automatic conversion of `MultiValueType` in `InformationRules` to `DMSRules`.

## [0.82.2] - 25-06-24
### Fixed
- Conversion from Information to DMS rules incorrectly set `nullable` for a property if
  the property had `min_value` not set in the Information rules. This is now fixed.

## [0.82.1] - 21-06-24
### Added
- added new entities `AssetEntity` and `RelationshipEntity`
- added new rules type `AssetRules`

## [0.82.0] - 21-06-24
### Added
- Introduce `query` module under `neat.graph` which holds previous `_Queries` class
- Added generation of `SPARQL` `CONSTRUCT` queries based on `rdfpath` transformations defined in `InformationRules`
- Introduce `NeatGraphStore.read` method which takes class and returns all instances of that class
- Test for `NeatGraphStore.read` method which entails end-to-end process of loading triples, inferring data model and reading instances of a class
### Changed
- `DMSLoader` now uses `.read` method of `NeatGraphStore`


## [0.81.12] - 20-06-24
### Added
- Placeholder for `NeatGraphStore.read_view` method
### Improved
- Simplified InformationArchitect rules by remove `rule_type` and renaming `rule` to `transformation` instead


## [0.81.11] - 19-06-24
### Added
- `AssetRelationshipConnector` transformer added
### Improved
- Handling of ids for labels and relationships


## [0.81.10] - 19-06-24
### Added
- `AssetEventConnector` transformer added

## [0.81.9] - 19-06-24
### Added
- `AssetFilesConnector` transformer added


## [0.81.8] - 19-06-24
### Added
- `AssetSequenceConnector` transformer added

## [0.81.7] - 19-06-24
### Added
- `AssetTimeSeriesConnector` transformer added

### Fixed
- `NeatGraphStore.transform` was resetting provenance object, this is now fixed


## [0.81.6] - 18-06-24
### Added
- Transformers module to NeatGraphStore
- `AddAssetDepth` transformer added

## [0.81.5] - 14-06-24
### Improved
- Dexpi Extractor is significantly more extracting triples from Dexpi XML files
- More human readable class and property ids in Dexpi Extractor


## [0.81.4] - 14-06-24
### Fixed
- When creating a new Enterprise model, node types are automatically created for all views. This is such that
  the node types can be used in the filters for any solution model built on top of the enterprise model.

## [0.81.3] - 14-06-24
### Fixed
- If external id of edge is longer than 256 characters it will be hashed to avoid exceeding the limit of 256 characters.


## [0.81.2] - 12-06-24
### Fixed
- When converting from Information to DMS rules, `neat` now automatically creates more containers if
  the number of properties exceeds the maximum number of properties per container. In addition, a warning
  is issued to the user if the number of properties exceeds the maximum number of properties per container.

## [0.81.1] - 12-06-24
### Improved
- Classic CDF extractors now prefix ids with resource type

### Removed
- Dependency on pytz


## [0.81.0] - 11-06-24
### Added
- `DexpiExtractor` graph extractor added.

## [0.80.3] - 12-06-24
### Fixed
- Increased upper bound on `python-multipart` dependency.

## [0.80.2] - 11-06-24
### Fixed
- Fixed missing input for `Reference data model id` in  `DMSToRules` step

## [0.80.1] - 11-06-24
### Fixed
- Fixed issues with duplicated edges when different properties are referring to the same target node.


## [0.80.0] - 10-06-24

### Improved
- Single `NeatGraphStore` instantiated via three options:
  - `from_memory_store`
  - `from_oxi_store`
  - `from_sparql_store`
### Removed
- Removed various superclassing of `NeatGraphStore`
- Remove Prometheus reminisce in code base
- Remove logging
### Added
- `RdfFileExtractor` graph extractor added.

## [0.79.0] - 10-06-24
### Added
- `TimeSeriesExtractor` graph extractor added.
- `SequencesExtractor` graph extractor added.
- `EventsExtractor` graph extractor added.
- `FilesExtractor` graph extractor added.
- `LabelsExtractor` graph extractor added.
- Dedicate test data for Classic CDF data model created
- Tracking of graph provenance added to `NeatGraphStore`

## [0.78.5] - 05-06-24
### Changed
- Increased upper bound on `fastapi` dependency.


## [0.78.4] - 05-06-24
### Added
- `AssetsExtractor` graph extractor added.

## [0.78.3] - 03-06-24
### Added
- `MultiValueType` for the Information Architect rules, allowing multiple value types for a property.

### Improved
- `InferenceImporter` is retaining information on multi value type for properties.

## [0.78.2] - 31-05-24
### Improved
- `OWLImporter` is now opinionated and will attempt to make the imported ontology compliant with the rules.

## [0.78.1] - 30-05-24
### Added
- Added `RulesInferenceFromRdfFile` to the step library

## [0.78.0] - 30-05-24
### Added
- `make_compliant` feature added to `InferenceImporter` producing compliant rules from a knowledge graph.

## [0.77.10] - 23-05-30
### Changed
- Increased upper bound on `uvicorn` dependency.

## [0.77.9] - 23-05-24
### Added
- `InferenceImporter` added to the core library enabling inference of rules from a graph.

## [0.77.8] - 23-05-24
### Fixed
- In the conversion form Information to DMS Rules, when referencing a class in reference rules, the implements
  was not set correctly. This is now fixed.
- In the new implementation of the conversion between Information and DMS rules, containers that already exist
  in a last or reference rule object were recreated. This is now fixed.

## [0.77.7] - 23-05-24
### Fixed
- In the `DMSImporter`, if you imported a data model with multiple views referencing the same direct property
  in a container, it would return an error. This is allowed and thus no longer return an error.
- There was an edge case that could cause the conversion between Information and DMS rules to fail with
  `MissingContainerError`. The conversion is now reimplemented to ensure that Information rules always
  will create the necessary containers in the conversion to DMS rules.

## [0.77.6] - 23-05-24
### Improves
- Documentation on how to use raw filter
- Added a simple example of Rules with raw filter
- Added new test for raw filter

## [0.77.5] - 23-05-24
### Fixed
- `DMSExporter` creates the schema depending on `extension` in metadata field as defined in the
  [documentation](https://cognite-neat.readthedocs-hosted.com/en/latest/terminology/rules-excel-input.html).

## [0.77.4] - 22-05-24
### Improves
- Information rules are now read using InformationRulesInput data class, replicate the form of DMS rules.
- Information rules are now serialized using dedicated serializer class
- Information rules are now validated using dedicated validator class
- Defaulting to "enterprise" data model type and "partial" schema completeness set to avoid validation error on import
### Fixed
- Fixed bug in `ExcelImporter` when importing a data model with a last spreadsheet and no reference model.
  This would trigger an error `RefMetadata sheet is missing or it failed` even though the
  ReferenceMetadata sheet is not needed.

## [0.77.3] - 14-05-24
### Fixed
- When using `DMSExporter` and importing a data model with a view pointing to a view not in the data model,
  it would fail to convert to an `Information` rules. This is now fixed.
- In the `ExcelExporter`, the `metadata` sheet is now created correctly when you use the arguments `dump_as="last"`,
  or `dump_as="reference"`, combined with and without `new_model_id`. **[Note]** The order of the `dump_as` and
  `new_model_id` arguments have switched places. This is to make it more intuitive to use the `ExcelExporter`
  as `new_model_id` is only relevant if `dump_as` is set to `last` or `reference`.

## [0.77.2] - 14-05-24
### Added
- Missing warning when `RawFilter` is used to warn users that the usage of this filter is not recommended.


## [0.77.1] - 14-05-24
### Added
- Support for `RawFilter` allow arbitrary filters to be applied to the data model.


## [0.77.0] - 13-05-24
### Changed
- [BREAKING] The subpackage `cognite.neat.rules.models` is reorganized. All imports using this subpackage must be
  updated.

### Added
- Support for exporting/importing `Last` spreadsheets in the `ExcelExporter` and `ExcelImporter`.
- [BREAKING] As a result of the above, in the `ExcelExporter` the parameter `is_reference` is replaced by `dump_as`.
  To continue using the old behavior, set `dump_as='reference'`.
- In the `DMSImporter.from_data_model_id`, now supports setting `reference_model_id` to download a solution model
  with a reference model.

## [0.76.3] - 10-05-24
### Added
- Added schema validator for performance, specifically if views map to too many containers.


## [0.76.2] - 06-05-24
### Fixed
- Added missing "Is Reference" parameter back to the `ExcelExporter`step.


## [0.76.1] - 06-05-24
### Changed
- Updated DMS Architect Rules template to fit the new DMS Rules structure
- Update Terminology/Rules to reflect new DMS Rules structure

## [0.76.0] - 06-05-24
### Removed
- [BREAKING] In `DMSRules`, `default_view_version` is no longer supported. Instead, you will now get a warning if view versions
  are not matching the data model version.

### Added/Changed
- [BREAKING] The following renaming of columns in `DMSRules`, properties sheet:
    - `Relation` -> `Connection`
    - `ViewProperty` -> `View Property`
    - `ContainerProperty` -> `Container Property`
    - `IsList` -> `Is List`
    - `Class` -> `Class (linage)`
    - `Property` -> `Property (linage)`
- [BREAKING] The following renaming of columns in `DMSRules`, views sheet:
    - `InModel` -> `In Model`
    - `Class` -> `Class (linage)`
- [BREAKING] The following renaming of columns in `DMSRules`, containers sheet:
    - `Class` -> `Class (linage)`
- [BREAKING] Added support for listable direct relations in `DMSRules`. In addition, there is now a complete reimplementation
  of the `connection` column in the `DMRRules` `properties` sheet.
- [BREAKING] Connection (former relation) can now be `direct`, `reverse`, or `edge`.
  While `multiedge` and `reversedirectc` have been removed. For more details,
  see the [DMS Rules Details](https://cognite-neat.readthedocs-hosted.com/en/latest/terminology/dmsrules.html#relation)
  documentation.
- In `DMSRules`, added support for setting containerId and nodeId in `View.Filter`. Earlier, only `nodeType` and
  `hasData` were supported which always used an implicit `containerId` and `nodeId` respectively. Now, the user can
  specify the node type and container id(s) by setting `nodeType(my_space:my_node_type)` and
  `hasData(my_space:my_container_id, my_space:my_other_container_id)`.
- Introduced, `dataModelType` in `DMSRules` and `InformationRules` to explicitly set the type of data model. This
  will be used to different types of validation and make the user aware of the type of data model they are working with.
- In `DMSExporter`, created smart defaults for setting `view.filters`. This is now recommended that the user uses
  the default values for `view.filters` and only set them explicitly if they now very well what they are doing.

## [0.75.9] - 04-05-24
### Improved
- Steps are now categorized as `current`, `legacy`, and `io` steps
- Workflow fails if one mix `current` and `legacy` steps in the same workflow

## [0.75.8] - 02-05-24
### Fixed
- `DMSExporter` now correctly exports direct relations with unknown source.

## [0.75.7] - 29-04-24
### Added
- `DMSExporter` now supports deletion of data model and data model components
- `DeleteDataModelFromCDF` added to the step library

## [0.75.6] - 26-04-24
### Changed
- All `NEAT` importers does not have `is_reference` parameter in `.to_rules()` method. This has been moved
  to the `ExcelExporter` `__init__` method. This is because this is the only place where this parameter was used.

### Added
- `DMSExporter` now supports skipping of export of `node_types`.

### Fixed
- When importing an `Excel` rules set with a reference model, the `ExcelImporter` would produce the warning
  `The copy method is deprecated; use the model_copy instead`. This is now fixed.

## [0.75.5] - 24-04-24
### Fixed
- Potential of having duplicated spaces are now fixed

## [0.75.4] - 24-04-24
### Fixed
- Rendering of correct metadata in UI for information architect
### Added
- Added `OntologyToRules` that works with V2 Rules (profiling)

## [0.75.3] - 23-04-24
### Fixed
- Names and descriptions were not considered for views and view properties

## [0.75.2] - 23-04-24
### Fixed
- Allowing that multiple View properties can map to the same Container property

## [0.75.1] - 23-04-24
### Fixed
- No spaces in any of the subfolders of the `neat` package.

## [0.75.0] - 23-04-24
### Added
- Added and moved all v1 rules related code base under `legacy` module

## [0.74.0] - 23-04-24
### Added
- added UI+api support for RulesV2. Read-only in the release , editable in the next release.

## [0.73.4] - 19-04-24
### Fixed
- updated urllib3 to 2.2.1

## [0.73.3] - 19-04-24
### Fixed
- updated uvicorn to 0.20.0
- updated fastapi to 0.110

## [0.73.2] - 19-04-24
### Fixed
- updated prometheus-client to 0.20.0

## [0.73.1] - 17-04-24
### Added
- Extended DEXPI for schemas 3.3 (no Attibute URI in genericAttributes and text without label parent).
### Fixed
- added missing py.typed (to enable mypy in projects using neat, ie docparser)

## [0.73.0] - 17-04-24
### Added
- Proper parsing/serialization of `inf`
- Added `new_model_id` to `ExcelExporter` to allow automatically setting metadata sheet when creating a new model
- In `DMSRules`, the user can now set `EdgeType` or `HasData` filter.
- The `DMSExporter` now validates data models wrt to a reference model, when `schema=extended`.

### Fixed
- In `DMSExporter`, `edge_type` is set correctly when referencing a multiedge property.
- Updated `cognite-sdk` to `7.37.0`, this broke neat with `ImportError: cannot import name 'ListablePropertyType'...`.
  This is now fixed.

### Removed
- The `DMSExporter` no longer has a `standardize_casing` parameter. Neat is no longer opinionated about casing.

## [0.72.3] - 16-04-24
### Fixed
- `ExcelImporter` was resetting `role` value to value set in rules instead of keeping value provided as arg
### Changed
- Default namespace set to `http://purl.org/cognite/neat#` instead of `http://purl.org/cognite/app#`
- OwlImporter for rules v2 has `make_compliant` set to False by default
### Added
- When creating OWL from rules, prefix will be saved under property `neat:prefix` (hence change of default namespace)
- When reading OWL if there is `neat:prefix` value will be added to `rules.metadata.prefix`
- By default we are defaulting OWL properties to min 0 and max 1 occurrence if no occurrence is set
- Added test for generation of complete rules out of partial rules

## [0.72.2] - 15-04-24
### Fixed
- `rules2dms` API route is now producing expected `View` objects to be visualized in CDF
### Added
- `publish-rules` API route added allowing publishing rules as DMS Schema components to CDF


## [0.72.1] - 11-04-24
### Fixed
- rdf:PlainLiteral and rdf:Literal was not resolving as string handled when exporting Rules to DMS schemas, this is now fixed
- OwlImporter that works with v2 rules was using `XSD_VALUE_TYPE_MAPPINGS` for v1 rules, this is now fixed
- added missing mapping for reference when converting information architect rules to dms architect rules

## [0.72.0] - 11-04-24
### Improved
- Improved garbadge collection process in workflows. Now all resources are properly released after workflow execution or reloading.
This is expecially critical when working with statfull objects like graph stores or big objects allocated in memory.
## Removed
- Removed a lot of old and stale code from workflows engine.
## Changed
- Changed CORS policy for UI to allow all origins. This is a temporary solution until it is properly configured in the future.

## [0.71.0] - 10-04-24
### Added
- Added `/api/core/rules2dms`
- Enabled conversion of rules to DMS views and containers

## [0.70.3] - 10-04-24
### Fixed
- Bug when importing an OWL ontology while expecting compliant rules did not encounter for dangling classes (classes without a property or parent class). This is now fixed.
### Improved
- Handling of xsd types as case insensitive when importing an OWL ontology.
### Added
- Handling of rdf:Literals in OWL ontology import as xsd:string

## [0.70.2] - 03-04-24
### Fixed
- Bug when exporting an `addition` to of a ruleset in  `DMSExporter` when using the method `.export_to_cdf`
### Changed
- Updated the `DMSExporter` to sort views in data model by (`space`, `external_id`).

## [0.70.1] - 03-04-24
### Added
- The `DMSExporter` now supports deploying an `addition` extension of a ruleset.

## [0.70.0] - 09-04-24
### Added
- Added `/api/core/convert`
- Enabled OWL importer to produce DMS rules


## [0.69.3] - 03-04-24
### Fixed
- Validation of `InformationRules` gives a warning if a reference class is used. This is now fixed.
- Validation of `InformationRules` returns an error if a importing a value type `Unknown`. This is now fixed.

## [0.69.2] - 03-04-24
### Fixed
- Fixed issue with `DMSImporter` when importing data models with direct relations without `source` set. This would
  cause a validation issue. This is now fixed.

## [0.69.1] - 03-04-24
### Fixed
- Fixed issue with `DMSImporter` when importing data models with data models that reference views outside the data model.
  This is now fixed.

## [0.69.0] - 03-04-24
### Added
- Experimental support for working with a reference model in the Rules.

### Fixed
- When using `DMSExporter` with `standardize_casing=False`, the `DMSExporter` would fail to export containers and
  views. This is now fixed.

### Changed
- When using any exporter writing to file, the default new line character and encoding of the OS was used. This is now
  changed to always use `utf-8` encoding and `'\n'` as the new line character. This is for working with **NEAT** in,
  for example, git-history, across multiple users with different OSes.
- In the `DMSExporter`, setting `existing_handling=force` will now also force the creation of `Containers` in addition
  to `Views`.

## [0.68.9] - 03-04-24
### Added
- Helper method `from_directory` and `from_zip_file` to `DMSExporter` to load DMS schema from directory or zip file.
  These methods are the complement of the `export_to_file()` method in `DMSExporter`.

## [0.68.8] - 25-03-24
### Fixed
- Remove harsh regex on Expected Value Types in Rules v1 DMS exporter


## [0.68.7] - 25-03-24
### Improved
- Input for DmsArchitect DMS value types are now case insensitive.


## [0.68.6] - 25-03-24
### Improved
- Input for InformationArchitect XSD value types are now case insensitive.


## [0.68.5] - 22-03-24
### Improved
- `ExcelExporter` and `YAMLExporter` now skips the default spaces and version when exporting rules.

## [0.68.4] - 22-03-24
### Fixed
- remove_namespace missed check weather namespace is of actual HTTP type


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
