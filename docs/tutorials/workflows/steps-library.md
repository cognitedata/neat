## Table of Contents

* [Graph Store](#graph-store)
* [Rules Exporter](#rules-exporter)
* [Input/Output](#input/output)
* [Graph Extractor](#graph-extractor)
* [Graph Loader](#graph-loader)
* [Rules Importer](#rules-importer)
* [Contextualization](#contextualization)
* [Graph Transformer](#graph-transformer)

## Graph Store

### ConfigureDefaultGraphStores

* **Category**: Graph Store
* **Version**: private-alpha
* **Description**: This step initializes the source and solution graph stores.
* **Input**: RulesData, NoneType
* **Output**: FlowMessage, SourceGraph, SolutionGraph

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| source_rdf_store.type | oxigraph | Data store type for source graph. Supported: oxigraph, memory,file, graphdb, sparql.  |
| solution_rdf_store.type | oxigraph | Data store type for solutioin graph. Supported: oxigraph, memory,file, graphdb, sparql |
| source_rdf_store.disk_store_dir | source-graph-store | Local directory for source graph store |
| source_rdf_store.query_url |  | Sparql query endpoint.Only for sparql and graphdb store type |
| source_rdf_store.update_url |  | Sparql update endpoint.Only for sparql and graphdb store type |
| solution_rdf_store.query_url |  | Sparql query endpoint.Only for sparql and graphdb store type |
| solution_rdf_store.update_url |  | Sparql update endpoint.Only for sparql and graphdb store type |
| solution_rdf_store.disk_store_dir | solution-graph-store | Local directory for solution graph store |
| stores_to_configure | all | Defines which stores to configure |
| solution_rdf_store.api_root_url |  | Root url for graphdb or sparql endpoint |

---


---

### ConfigureGraphStore

* **Category**: Graph Store
* **Version**: private-beta
* **Description**: This step initializes the source and solution graph stores.
* **Input**: RulesData, NoneType
* **Output**: FlowMessage, SourceGraph, SolutionGraph

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| graph_name | source | Name of the data store. Supported: solution, source  |
| store_type | oxigraph | Data store type for source graph. Supported: oxigraph, memory,file, graphdb, sparql.  |
| disk_store_dir | source-graph-store | Local directory that is used as local graph store.Only for oxigraph, file store types |
| sparql_query_url |  | Query url for sparql endpoint.Only for sparql store type |
| sparql_update_url |  | Update url for sparql endpoint.Only for sparql store type |
| db_server_api_root_url |  | Root url for graphdb or sparql endpoint.Only for graphdb |
| init_procedure | reset | Operations to be performed on the graph store as part of init and configuration process.               Supported options : reset, clear, none |

---


---

### ResetGraphStores

* **Category**: Graph Store
* **Version**: private-alpha
* **Description**: This step resets graph stores to their initial state (clears all data).
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| graph_name | source | Name of the data store. Supported: solution, source  |

---


---

## Rules Exporter

### DeleteDMSSchemaComponents

* **Category**: Rules Exporter
* **Version**: private-alpha
* **Description**: This step deletes DMS Data model and all underlying containers and views.
* **Input**: DMSSchemaComponentsData, CogniteClient
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| components |  | Select which DMS schema component(s) to delete |
| multi_space_components_removal | False | False (default) = Only delete components inside the space referred in Metadata Sheet of Rules, True = Delete all components referred to in Rules<\p> |

---


---

### ExportDMSSchemaComponentsToCDF

* **Category**: Rules Exporter
* **Version**: private-alpha
* **Description**: This step exports generated DMS Schema components to CDF.
* **Input**: DMSSchemaComponentsData, CogniteClient
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| components |  | Select which DMS schema component(s) to export to CDF |
| existing_component_handling | fail | How to handle situation when components being exported in CDF already exist.Fail the step if any component already exists, Skip the component if it already exists,  or Update the component try to update the component. |
| multi_space_components_create | False | Whether to create only components belonging to the data model space (i.e. space define under Metadata sheet of Rules), or also additionally components outside of the data model space. |

---


---

### ExportDMSSchemaComponentsToYAML

* **Category**: Rules Exporter
* **Version**: private-alpha
* **Description**: This step exports DMS schema components as YAML files
* **Input**: DMSSchemaComponentsData
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| storage_dir | staging | Directory to store DMS schema files |
| format | yaml-dump | Format of the output files |

---


---

### ExportDataModelStorage

* **Category**: Rules Exporter
* **Version**: private-beta
* **Description**: This step exports generated DMS Schema to CDF.
* **Input**: MultiRuleData, CogniteClient
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| dry_run | False | Whether to perform a dry run of the export.  |
| components |  | Select which DMS schema component(s) to export to CDF |
| existing_component_handling | fail | How to handle situation when components being exported in CDF already exist.Fail the step if any component already exists, Skip the component if it already exists,  or Update the component try to update the component. |
| multi_space_components_create | False | Whether to create only components belonging to the data model space (i.e. space define under Metadata sheet of Rules), or also additionally components outside of the data model space. |

---


---

### ExportRulesToExcel

* **Category**: Rules Exporter
* **Version**: private-alpha
* **Description**: This step export Rules to Excel representation
* **Input**: RulesData
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| output_file_path | rules/custom-rules.xlsx | File path to the generated Excel file |

---


---

### ExportRulesToGraphCapturingSheet

* **Category**: Rules Exporter
* **Version**: private-alpha
* **Description**: This step generates graph capturing sheet
* **Input**: RulesData
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| file_name | graph_capture_sheet.xlsx | File name of the data capture sheet |
| auto_identifier_type | index-based | Type of automatic identifier |
| storage_dir | staging | Directory to store data capture sheets |

---


---

### ExportRulesToGraphQLSchema

* **Category**: Rules Exporter
* **Version**: private-alpha
* **Description**: This step generates GraphQL schema from data model defined in transformation rules.
* **Input**: RulesData
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| file_name |  | Name of the GraphQL schema file it must have .graphql extension, if empty defaults to form `prefix-version.graphql` |
| storage_dir | staging | Directory to store GraphQL schema file |

---


---

### ExportRulesToOntology

* **Category**: Rules Exporter
* **Version**: private-alpha
* **Description**: This step exports Rules to OWL ontology
* **Input**: RulesData
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| ontology_file_path | staging/ontology.ttl | Relative path for the ontology file storage, must end with .ttl ! Will be auto-created if not provided ! |

---


---

### ExportRulesToSHACL

* **Category**: Rules Exporter
* **Version**: private-alpha
* **Description**: This step exports Rules to SHACL
* **Input**: RulesData
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| shacl_file_path | staging/shacl.ttl | Relative path for the SHACL file storage, must end with .ttl ! Will be auto-created if not provided ! |

---


---

### ExportToExcel

* **Category**: Rules Exporter
* **Version**: private-beta
* **Description**: This step exports generated Excel rules.
* **Input**: MultiRuleData
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| styling | default | Styling of the Excel file |

---


---

### GenerateDMSSchemaComponentsFromRules

* **Category**: Rules Exporter
* **Version**: private-alpha
* **Description**: This step generates DMS Schema components, such as data model, views, containers, etc. from Rules.
* **Input**: RulesData
* **Output**: FlowMessage, DMSSchemaComponentsData

---


---

## Input/Output

### DownloadDataFromRestApiToFile

* **Category**: Input/Output
* **Version**: private-beta
* **Description**: This step downloads the response from a REST API and saves it to a file.
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| api_url |  | API URL |
| output_file_path | workflows/workflow_name/output.json | Output File Path. The path must be relative to the data store path. |
| http_method | GET | HTTP Method (GET/POST/PUT) |
| auth_mode | none | Authentication Mode (basic/token/none) |
| username |  | Username (for basic auth) |
| password |  | Password (for basic auth) |
| token |  | Token (for token auth) |
| response_destination | file | Destination for the response (file/flow_message/both) |
| http_headers |  | Custom HTTP headers separated by ';' . Example:               'Content-Type: application/json; Accept: application/json' |

---


---

### DownloadFileFromCDF

* **Category**: Input/Output
* **Version**: private-beta
* **Description**: This step fetches and stores file from CDF
* **Input**: CogniteClient
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| cdf.external_id |  | External ID of the file stored in CDF |
| local.file_name |  | The name of the file under which the content will be stored locally |
| local.storage_dir | rules/ | The directory where the file will be stored |

---


---

### DownloadFileFromGitHub

* **Category**: Input/Output
* **Version**: private-beta
* **Description**: This step fetches and stores the file from private Github repository
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| github.filepath |  | File path to the file stored on Github |
| github.personal_token |  | Github Personal Access Token which allows fetching file from private Github repository |
| github.owner |  | Github repository owner, also know as github organization |
| github.repo |  | Github repository from which the file is being fetched |
| github.branch | main | Github repository branch from which the file is being fetched |
| local.file_name |  | The name of the file under which it will be stored locally |
| local.storage_dir | rules/ | The directory where the file will be stored |

---


---

### UploadFileToCDF

* **Category**: Input/Output
* **Version**: private-beta
* **Description**: This step uploads file to CDF
* **Input**: CogniteClient
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| cdf.external_id |  | Exernal Id for the file to be stored in CDF |
| cdf.dataset_id |  | Dataset Id for the file to be stored in CDF. Must be a number |
| local.file_name |  | The name of the local file to be uploaded to CDF |
| local.storage_dir | rules/ | Local directory where the file is stored |

---


---

### UploadFileToGitHub

* **Category**: Input/Output
* **Version**: private-beta
* **Description**: This step uploads file to private Github repository
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| github.filepath |  | File path to the file stored on Github |
| github.personal_token |  | Github Personal Access Token which allows uploading file to private Github repository |
| github.owner |  | Github repository owner, also know as github organization |
| github.repo |  | Github repository the file is being uploaded to |
| github.branch | main | Github repository branch the file is being uploaded to |
| github.commit_message | New file | The commit message to be used when uploading the file |
| local.file_name |  | The name of the local file to be uploaded to Github |
| local.storage_dir | rules/ | Local directory where the file is stored |

---


---

### ValidateAgainstCDF

* **Category**: Input/Output
* **Version**: private-beta
* **Description**: This step downloads the response from a REST API and saves it to a file.
* **Input**: MultiRuleData, CogniteClient
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| Report Formatter | BasicHTML | The format of the report for the validation of the rules |

---


---

## Graph Extractor

### ExtractGraphFromAvevaPiAssetFramework

* **Category**: Graph Extractor
* **Version**: private-alpha
* **Description**: This step extracts instances from Aveva PI AF and loads them into a graph store
* **Input**: FlowMessage, SolutionGraph, SourceGraph
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| file_name | staging/pi_af_dump.xml | Full path to the file             containing data dump in XML format |
| graph_name | solution | The name of target graph. |
| root_node_external_id | root | External id of the root node. The node will be created if it doesn't exist |
| root_node_name | root | Name of the root node. The node will be created if it doesn't exist |
| root_node_type | Asset | Type of the root node. The node will be created if it doesn't exist |
| namespace | http://purl.org/cognite/neat# | Namespace to be used for the generated objects. |
| namespace_prefix | neat | The prefix to be used for the namespace. |

---


---

### ExtractGraphFromDexpiFile

* **Category**: Graph Extractor
* **Version**: private-alpha
* **Description**: This step converts DEXPI P&ID (XML) into Knowledge Graph
* **Input**: SourceGraph
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| file_path | source-graphs/dexpi-pid.xml | File path to DEXPI P&ID in XML format |
| base_namespace | http://purl.org/cognite/neat# | Base namespace to be added to ids for all nodes found in P&ID |

---


---

### ExtractGraphFromGraphCapturingSheet

* **Category**: Graph Extractor
* **Version**: private-alpha
* **Description**: This step extracts nodes and edges from graph capturing spreadsheet and load them into graph
* **Input**: RulesData, SolutionGraph, SourceGraph
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| file_path | source-graphs/graph_capture_sheet.xlsx | File path to Graph Capturing Sheet |
| base_namespace | http://purl.org/cognite/neat# | Base namespace to be added to ids for all nodes extracted from graph capturing spreadsheet |
| graph_name | solution | The name of target graph to load nodes and edge sto. |

---


---

### ExtractGraphFromJsonFile

* **Category**: Graph Extractor
* **Version**: private-alpha
* **Description**: This step extracts instances from json file and loads them into a graph store
* **Input**: SolutionGraph, SourceGraph
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| file_name | data_dump.json | Full path to the file containing data dump in JSON format |
| graph_name | solution | The name of target graph. |
| object_id_generation_method | hash_of_json_element | Method to be used for generating object ids.                   source_object_properties - takes multiple properties from the source object and concatenates them.                  source_object_id_mapping - takes a single property from the                  source object and maps it to a instance id.                       The option should be used when source object already contains stable ids                 hash_of_json_element - takes a hash of the JSON element.Very generic method but                      can be slow working with big objects.                 uuid - generates a random UUID, the option produces unstables ids .  |
| json_object_id_mapping | name | Comma separated list of object properties to be used for generating object ids.             Each property must be prefixed with the name of the object. For example: device:name,pump:id |
| json_object_labels_mapping |  | Comma separated list of object properties to be used for generating object labels.             Each property must be prefixed with the name of the object. For example: asset:name,asset:type |
| namespace | http://purl.org/cognite/neat# | Namespace to be used for the generated objects. |
| namespace_prefix | neat | The prefix to be used for the namespace. |

---


---

### ExtractGraphFromMockGraph

* **Category**: Graph Extractor
* **Version**: private-alpha
* **Description**: This step extracts instances from graph capture spreadsheet and loads them into solution graph
* **Input**: RulesData, SolutionGraph, SourceGraph
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| class_count | {"GeographicalRegion":5, "SubGeographicalRegion":10} | Target number of instances for each class |
| graph_name | solution | The name of target graph. |

---


---

### ExtractGraphFromRdfFile

* **Category**: Graph Extractor
* **Version**: private-beta
* **Description**: This step extract instances from a file into the source graph. The file must be in RDF format.
* **Input**: SourceGraph
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| file_path | source-graphs/source-graph-dump.xml | File name of source graph data dump in RDF format |
| mime_type | application/rdf+xml | MIME type of file containing RDF graph |
| add_base_iri | True | Whether to add base IRI to graph in case if entity ids are relative |

---


---

### ExtractGraphFromRulesDataModel

* **Category**: Graph Extractor
* **Version**: private-alpha
* **Description**: This step extracts data model from rules file and loads it into source graph.
* **Input**: RulesData, SourceGraph
* **Output**: FlowMessage

---


---

### ExtractGraphFromRulesInstanceSheet

* **Category**: Graph Extractor
* **Version**: private-alpha
* **Description**: This step extracts instances from Rules object and loads them into the graph.
* **Input**: RulesData, SolutionGraph, SourceGraph
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| graph_name | solution | The name of target graph. |

---


---

## Graph Loader

### GenerateAssetsFromGraph

* **Category**: Graph Loader
* **Version**: private-alpha
* **Description**: The step generates assets from the graph ,categorizes them and stores them in CategorizedAssets object
* **Input**: RulesData, CogniteClient, SolutionGraph
* **Output**: FlowMessage, CategorizedAssets

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| data_set_id |  | CDF dataset id to which the labels will be added. |
| asset_external_id_prefix |  | Prefix to be added to all asset external ids, default None. |
| assets_cleanup_type | nothing | Configures asset cleanup process. Supported options: nothing - no cleanup,                     orphans - all orphan assets will be removed, circular - all circular assets will be removed ,                     full - full cleanup , both orphans and circular assets will be removed.  |

---


---

### GenerateNodesAndEdgesFromGraph

* **Category**: Graph Loader
* **Version**: 1.0.0
* **Description**: The step generates nodes and edges from the graph
* **Input**: RulesData, SourceGraph, SolutionGraph
* **Output**: FlowMessage, Nodes, Edges

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| graph_name | source | The name of the graph to be used for matching. Supported options : source, solution |
| add_class_prefix | False | Whether to add class name as a prefix to external ids of instances or not |
| data_validation_error_handling_strategy | skip_and_report | The strategy for handling data validation errors. Supported options:                    skip_and_report - failed instance (node or edge) will be skipped and reported ,                    fail_and_report - failed instance  (node or edge) will fail the workflow and report the error |

---


---

### GenerateRelationshipsFromGraph

* **Category**: Graph Loader
* **Version**: private-alpha
* **Description**: This step generates relationships from the graph and saves them to CategorizedRelationships object
* **Input**: RulesData, CogniteClient, SolutionGraph
* **Output**: FlowMessage, CategorizedRelationships

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| data_set_id |  | CDF dataset id to which the labels will be added. |
| relationship_external_id_prefix |  | Prefix to be added to all asset external ids, default None. |

---


---

### LoadAssetsToCDF

* **Category**: Graph Loader
* **Version**: private-alpha
* **Description**: This step uploads categorized assets to CDF
* **Input**: CogniteClient, CategorizedAssets, FlowMessage
* **Output**: FlowMessage

---


---

### LoadEdgesToCDF

* **Category**: Graph Loader
* **Version**: private-alpha
* **Description**: This step uploads edges to CDF
* **Input**: CogniteClient, Edges
* **Output**: FlowMessage

---


---

### LoadGraphToRdfFile

* **Category**: Graph Loader
* **Version**: private-beta
* **Description**: The step generates nodes and edges from the graph
* **Input**: SourceGraph, SolutionGraph
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| graph_name | source | The name of the graph to be used for loading RDF File. Supported options : source, solution |
| rdf_file_path | staging/graph_export.ttl | Relative path for the RDF file storage, must end with .ttl ! |

---


---

### LoadLabelsToCDF

* **Category**: Graph Loader
* **Version**: private-alpha
* **Description**: This step creates default NEAT labels in CDF
* **Input**: RulesData, CogniteClient

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| data_set_id |  | CDF dataset id to which the labels will be added. |

---


---

### LoadNodesToCDF

* **Category**: Graph Loader
* **Version**: private-alpha
* **Description**: This step uploads nodes to CDF
* **Input**: CogniteClient, Nodes
* **Output**: FlowMessage

---


---

### LoadRelationshipsToCDF

* **Category**: Graph Loader
* **Version**: private-alpha
* **Description**: This step uploads relationships to CDF
* **Input**: CogniteClient, CategorizedRelationships
* **Output**: FlowMessage

---


---

## Rules Importer

### ImportArbitraryJsonYamlToRules

* **Category**: Rules Importer
* **Version**: private-alpha
* **Description**: The step extracts schema from arbitrary json file and generates NEAT transformation rules object.
* **Output**: FlowMessage, RulesData

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| file_path | workflows/openapi_to_rules/data/data.json | Relative path to the json file.The file can be in either json or in yaml format. |
| fdm_compatibility_mode | True | If set to True, the step will try to convert property names to FDM compatible names. |

---


---

### ImportExcelToRules

* **Category**: Rules Importer
* **Version**: private-alpha
* **Description**: This step import rules from the Excel file
* **Input**: CdfStore
* **Output**: FlowMessage, RulesData

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| validation_report_storage_dir | rules_validation_report | Directory to store validation report |
| validation_report_file | rules_validation_report.txt | File name to store validation report |
| file_name | rules.xlsx | Full name of the rules file in rules folder. If includes path,                 it will be relative to the neat data folder |
| version |  | Optional version of the rules file |

---


---

### ImportExcelValidator

* **Category**: Rules Importer
* **Version**: private-beta
* **Description**: This step imports rules from an excel file
* **Input**: FlowMessage
* **Output**: FlowMessage, MultiRuleData

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| Report Formatter | BasicHTML | The format of the report for the validation of the rules |
| role | infer | For what role Rules are intended? |

---


---

### ImportFromDataModelStorage

* **Category**: Rules Importer
* **Version**: private-beta
* **Description**: This step imports rules from CDF Data Model
* **Input**: CogniteClient
* **Output**: FlowMessage, MultiRuleData

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| Data Model ID |  | The ID of the Data Model to import. Written at 'my_space:my_data_model(version=1)' |
| Report Formatter | BasicHTML | The format of the report for the validation of the rules |
| role | infer | For what role Rules are intended? |

---


---

### ImportGraphToRules

* **Category**: Rules Importer
* **Version**: private-alpha
* **Description**: The step extracts data model from RDF graph and generates NEAT transformation rules object.     The rules object can be serialized to excel file or used directly in other steps.
* **Input**: SourceGraph, SolutionGraph
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| excel_file_path | staging/rules.xlsx | Relative path for the Excel rules storage. |
| max_number_of_instances | -1 | Maximum number of instances per class to process, -1 means all instances |

---


---

### ImportOntologyToRules

* **Category**: Rules Importer
* **Version**: private-alpha
* **Description**: The step extracts NEAT rules object from OWL Ontology and         exports them as an Excel rules files for further editing.
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| ontology_file_path | staging/ontology.ttl | Relative path to the OWL ontology file. |
| excel_file_path | staging/rules.xlsx | Relative path for the Excel rules storage. |
| make_compliant | True | Relative path for the Excel rules storage. |

---


---

### ImportOpenApiToRules

* **Category**: Rules Importer
* **Version**: private-alpha
* **Description**: The step extracts schema from OpenAPI specification and generates NEAT transformation rules object.     The rules object can be serialized to excel file or used directly in other steps.
* **Output**: FlowMessage, RulesData

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| openapi_spec_file_path | workflows/openapi_to_rules/source_data/openapi.json | Relative path to the OpenAPI spec file.The file can be in either json or in yaml format. |
| fdm_compatibility_mode | True | If set to True, the step will try to convert property names to FDM compatible names. |

---


---

## Contextualization

### SimpleGraphEntityMatcher

* **Category**: Contextualization
* **Version**: private-alpha
* **Description**: The step matches entities in the graph and creates links based on provided configurations
* **Input**: SolutionGraph, SourceGraph
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| source_class |  | Name of the source class |
| source_property |  | Name of the source property |
| source_value_type | single_value_str | Type of the value in the source property.Propery can have single value               or multiple values separated by comma. |
| target_class |  | Name of the target class |
| target_property |  | Name of the target property |
| relationship_name | link | Label of the relationship to be created |
| link_direction | target_to_source | Direction of the relationship. |
| matching_method | regexp | Method to be used for matching. Supported options . |
| graph_name | source | The name of the graph to be used for matching. |
| link_namespace | http://purl.org/cognite/neat# | The namespace of the link to be created |

---


---

## Graph Transformer

### TransformSourceToSolutionGraph

* **Category**: Graph Transformer
* **Version**: private-alpha
* **Description**: The step transforms source graph to solution graph
* **Input**: RulesData, CogniteClient, SourceGraph, SolutionGraph
* **Output**: FlowMessage

**Configurables:**

| Name | Default value | Description |
| ---- | ----- | ----- |
| cdf_lookup_database |  | Name of the CDF raw database to use for data lookup (rawlookup rules).            Applicable only for transformations with rawlookup rules. |

---


---
