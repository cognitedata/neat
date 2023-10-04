## ArbitraryJsonYamlToRules

* **Description**: The step extracts schema from arbitrary json file and generates NEAT transformation rules object.
* **Category**: Rules Importer
* **Scope**: core_global
* **Output**: FlowMessage, RulesData
* **Configurables**:
  - *file_path*: workflows/openapi_to_rules/data/data.json
  - *fdm_compatibility_mode*: True
* **Version**: 0.1.0-alpha
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## ConfigureDefaultGraphStores

* **Description**: This step initializes the source and solution graph stores.
* **Category**: Graph Store
* **Scope**: core_global
* **Input**: RulesData
* **Output**: FlowMessage, SourceGraph, SolutionGraph
* **Configurables**:
  - *source_rdf_store.type*: oxigraph
  - *solution_rdf_store.type*: oxigraph
  - *source_rdf_store.disk_store_dir*: source-graph-store
  - *source_rdf_store.query_url*:
  - *source_rdf_store.update_url*:
  - *solution_rdf_store.query_url*:
  - *solution_rdf_store.update_url*:
  - *solution_rdf_store.disk_store_dir*: solution-graph-store
  - *stores_to_configure*: all
  - *solution_rdf_store.api_root_url*:
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## ConfigureGraphStore

* **Description**: This step initializes the source and solution graph stores.
* **Category**: Graph Store
* **Scope**: core_global
* **Input**: RulesData
* **Output**: FlowMessage, SourceGraph, SolutionGraph
* **Configurables**:
  - *graph_name*: source
  - *store_type*: oxigraph
  - *disk_store_dir*: source-graph-store
  - *sparql_query_url*:
  - *sparql_update_url*:
  - *db_server_api_root_url*:
  - *init_procedure*: reset
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## CreateCDFLabels

* **Description**: This step creates default NEAT labels in CDF
* **Category**: Graph Loader
* **Scope**: core_global
* **Input**: RulesData, CogniteClient
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## DMSDataModelFromRules

* **Description**: This step generates DMS Data model from data model defined in transformation rules.
* **Category**: Rules Exporter
* **Scope**: core_global
* **Input**: RulesData
* **Output**: FlowMessage, DMSDataModel
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## DataModelFromRulesToSourceGraph

* **Description**: This step extracts data model from rules file and loads it into source graph.
* **Category**: Graph Extractor
* **Scope**: core_global
* **Input**: RulesData, SourceGraph
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## DeleteDMSDataModel

* **Description**: This step deletes DMS Data model and all underlying containers and views.
* **Category**: Rules Exporter
* **Scope**: core_global
* **Input**: DMSDataModel, CogniteClient
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## DownloadDataFromRestApiToFile

* **Description**: This step downloads the response from a REST API and saves it to a file.
* **Category**: Input/Output
* **Scope**: core_global
* **Output**: FlowMessage
* **Configurables**:
  - *api_url*:
  - *output_file_path*: workflows/workflow_name/output.json
  - *http_method*: GET
  - *auth_mode*: none
  - *username*:
  - *password*:
  - *token*:
  - *response_destination*: file
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## DownloadFileFromCDF

* **Description**: This step fetches and stores file from CDF
* **Category**: Input/Output
* **Scope**: core_global
* **Input**: CogniteClient
* **Output**: FlowMessage
* **Configurables**:
  - *cdf.external_id*:
  - *local.file_name*:
  - *local.storage_dir*: rules/
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## DownloadFileFromGitHub

* **Description**: This step fetches and stores the file from private Github repository
* **Category**: Input/Output
* **Scope**: core_global
* **Output**: FlowMessage
* **Configurables**:
  - *github.filepath*:
  - *github.personal_token*:
  - *github.owner*:
  - *github.repo*:
  - *github.branch*: main
  - *local.file_name*:
  - *local.storage_dir*: rules/
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## ExcelFromRules

* **Description**: The step generates Excel file from rules
* **Category**: Rules Exporter
* **Scope**: core_global
* **Input**: RulesData
* **Output**: FlowMessage
* **Configurables**:
  - *output_file_path*: rules/custom-rules.xlsx
* **Version**: 0.1.0-alpha
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## GenerateCDFAssetsFromGraph

* **Description**: The step generates assets from the graph ,categorizes them and stores them in CategorizedAssets object
* **Category**: Graph Loader
* **Scope**: core_global
* **Input**: RulesData, CogniteClient, SolutionGraph
* **Output**: FlowMessage, CategorizedAssets
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## GenerateCDFNodesAndEdgesFromGraph

* **Description**: The step generates nodes and edges from the graph
* **Category**: Graph Loader
* **Scope**: core_global
* **Input**: RulesData, SourceGraph, SolutionGraph
* **Output**: FlowMessage, Nodes, Edges
* **Configurables**:
  - *graph_name*: source
  - *add_class_prefix*: False
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## GenerateCDFRelationshipsFromGraph

* **Description**: This step generates relationships from the graph and saves them to CategorizedRelationships object
* **Category**: Graph Loader
* **Scope**: core_global
* **Input**: RulesData, CogniteClient, SolutionGraph
* **Output**: FlowMessage, CategorizedRelationships
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## GenerateMockGraph

* **Description**: This step extracts instances from graph capture spreadsheet and loads them into solution graph
* **Category**: Graph Extractor
* **Scope**: core_global
* **Input**: RulesData, SolutionGraph, SourceGraph
* **Output**: FlowMessage
* **Configurables**:
  - *class_count*: {"GeographicalRegion":5, "SubGeographicalRegion":10}
  - *graph_name*: solution
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## GraphCaptureSpreadsheetFromRules

* **Description**: This step generates data capture spreadsheet from data model defined in rules
* **Category**: Rules Exporter
* **Scope**: core_global
* **Input**: RulesData
* **Output**: FlowMessage
* **Configurables**:
  - *file_name*: graph_capture_sheet.xlsx
  - *auto_identifier_type*: index-based
  - *storage_dir*: staging
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## GraphQLSchemaFromRules

* **Description**: This step generates GraphQL schema from data model defined in transformation rules.
* **Category**: Rules Exporter
* **Scope**: core_global
* **Input**: RulesData
* **Output**: FlowMessage
* **Configurables**:
  - *file_name*:
  - *storage_dir*: staging
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## InstancesFromGraphCaptureSpreadsheetToGraph

* **Description**: This step extracts instances from graph capture spreadsheet and loads them into solution graph
* **Category**: Graph Extractor
* **Scope**: core_global
* **Input**: RulesData, SolutionGraph, SourceGraph
* **Output**: FlowMessage
* **Configurables**:
  - *file_name*: graph_capture_sheet.xlsx
  - *storage_dir*: staging
  - *graph_name*: solution
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## InstancesFromJsonToGraph

* **Description**: This step extracts instances from json file and loads them into a graph store
* **Category**: Graph Extractor
* **Scope**: core_global
* **Input**: SolutionGraph, SourceGraph
* **Output**: FlowMessage
* **Configurables**:
  - *file_name*: data_dump.json
  - *graph_name*: solution
  - *object_id_generation_method*: hash_of_json_element
  - *json_object_id_mapping*: name
  - *json_object_labels_mapping*:
  - *namespace*: http://purl.org/cognite/neat#
  - *namespace_prefix*: neat
* **Version**: 0.1.0-alpha
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## InstancesFromRdfFileToSourceGraph

* **Description**: This step extract instances from a file into the source graph. The file must be in RDF format.
* **Category**: Graph Extractor
* **Scope**: core_global
* **Input**: RulesData, SourceGraph
* **Output**: FlowMessage
* **Configurables**:
  - *file_path*: source-graphs/source-graph-dump.xml
  - *mime_type*: application/rdf+xml
  - *add_base_iri*: True
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## InstancesFromRulesToSolutionGraph

* **Description**: This step extracts instances from rules file and loads them into solution graph.
* **Category**: Graph Extractor
* **Scope**: core_global
* **Input**: RulesData, SolutionGraph
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## LoadTransformationRules

* **Description**: This step loads transformation rules from the file or remote location
* **Category**: Rules Parser
* **Scope**: core_global
* **Input**: CdfStore
* **Output**: FlowMessage, RulesData
* **Configurables**:
  - *validation_report_storage_dir*: rules_validation_report
  - *validation_report_file*: rules_validation_report.txt
  - *file_name*: rules.xlsx
  - *version*:
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## OntologyFromRules

* **Description**: This step generates OWL ontology from data model defined in transformation rules.
* **Category**: Rules Exporter
* **Scope**: core_global
* **Input**: RulesData
* **Output**: FlowMessage
* **Configurables**:
  - *file_name*:
  - *storage_dir*: staging
  - *store_warnings*: True
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## OpenApiToRules

* **Description**: The step extracts schema from OpenAPI specification and generates NEAT transformation rules object.     The rules object can be serialized to excel file or used directly in other steps.
* **Category**: Rules Importer
* **Scope**: core_global
* **Output**: FlowMessage, RulesData
* **Configurables**:
  - *openapi_spec_file_path*: workflows/openapi_to_rules/source_data/openapi.json
  - *fdm_compatibility_mode*: True
* **Version**: 0.1.0-alpha
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## ResetGraphStores

* **Description**: This step resets graph stores to their initial state (clears all data).
* **Category**: Graph Store
* **Scope**: core_global
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## SHACLFromRules

* **Description**: This step generates SHACL from data model defined in transformation rules
* **Category**: Rules Exporter
* **Scope**: core_global
* **Input**: RulesData
* **Output**: FlowMessage
* **Configurables**:
  - *file_name*:
  - *storage_dir*: staging
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## SimpleGraphEntityMatcher

* **Description**: The step matches entities in the graph and creates links based on provided configurations
* **Category**: contextualization
* **Scope**: core_global
* **Input**: SolutionGraph, SourceGraph
* **Output**: FlowMessage
* **Configurables**:
  - *source_class*:
  - *source_property*:
  - *source_value_type*: single_value_str
  - *target_class*:
  - *target_property*:
  - *relationship_name*: link
  - *link_direction*: target_to_source
  - *matching_method*: regexp
  - *graph_name*: source
  - *link_namespace*: http://purl.org/cognite/neat#
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## TransformSourceToSolutionGraph

* **Description**: The step transforms source graph to solution graph
* **Category**: Graph Transformer
* **Scope**: core_global
* **Input**: RulesData, CogniteClient, SourceGraph, SolutionGraph
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## UploadCDFAssets

* **Description**: This step uploads categorized assets to CDF
* **Category**: Graph Loader
* **Scope**: core_global
* **Input**: RulesData, CogniteClient, CategorizedAssets, FlowMessage
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## UploadCDFEdges

* **Description**: This step uploads edges to CDF
* **Category**: Graph Loader
* **Scope**: core_global
* **Input**: CogniteClient, Edges
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## UploadCDFNodes

* **Description**: This step uploads nodes to CDF
* **Category**: Graph Loader
* **Scope**: core_global
* **Input**: CogniteClient, Nodes
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## UploadCDFRelationships

* **Description**: This step uploads relationships to CDF
* **Category**: Graph Loader
* **Scope**: core_global
* **Input**: CogniteClient, CategorizedRelationships
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## UploadDMSDataModel

* **Description**: This step uploaded generated DMS Data model.
* **Category**: Rules Exporter
* **Scope**: core_global
* **Input**: DMSDataModel, CogniteClient
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## UploadFileToCDF

* **Description**: This step uploads file to CDF
* **Category**: Input/Output
* **Scope**: core_global
* **Input**: CogniteClient
* **Output**: FlowMessage
* **Configurables**:
  - *cdf.external_id*:
  - *cdf.dataset_id*:
  - *local.file_name*:
  - *local.storage_dir*: rules/
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## UploadFileToGitHub

* **Description**: This step uploads file to private Github repository
* **Category**: Input/Output
* **Scope**: core_global
* **Output**: FlowMessage
* **Configurables**:
  - *github.filepath*:
  - *github.personal_token*:
  - *github.owner*:
  - *github.repo*:
  - *github.branch*: main
  - *github.commit_message*: New file
  - *local.file_name*:
  - *local.storage_dir*: rules/
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## AssetCounter

* **Description**: Return count of assets
* **Category**: test
* **Scope**: user_global
* **Input**: CogniteClient
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## LogFlowMessage

* **Description**: Flow message logger
* **Category**: test
* **Scope**: user_global
* **Input**: FlowMessage
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## RunIdReporter

* **Description**: Return count of assets
* **Category**: test
* **Scope**: user_global
* **Input**: CogniteClient
* **Output**: FlowMessage
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## FlowMessageFileLogger

* **Description**: Writes flow message to file
* **Category**: test
* **Scope**: stdsteps_tester
* **Input**: FlowMessage
* **Output**: FlowMessage
* **Configurables**:
  - *file_path*: flow_message.log
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## FlowMessageFileLogger2

* **Description**: Writes flow message to file2
* **Category**: test
* **Scope**: stdsteps_tester
* **Input**: FlowMessage
* **Output**: FlowMessage
* **Configurables**:
  - *file_path*: flow_message.log
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---

## LoadAndParseTimeseriesMetadataIntoSourceGraph

* **Description**: The step loads timeseries metadata from CSV file and parses it into the source graph
* **Category**: wdea
* **Scope**: wdea_assets
* **Input**: SourceGraph
* **Output**: FlowMessage
* **Configurables**:
  - *source_file*: workflows/wdea_assets/source_data/wdea_timeseries.csv
* **Version**: 1.0.0
* **Docs URL**: [https://cognite-neat.readthedocs-hosted.com/en/latest/](https://cognite-neat.readthedocs-hosted.com/en/latest/)
* **Source**: cognite

---
