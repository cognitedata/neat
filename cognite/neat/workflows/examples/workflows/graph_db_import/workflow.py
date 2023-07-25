import logging
import time
from pathlib import Path

import requests
from cognite.client import CogniteClient

from cognite.neat.core.loader.graph_store import NeatGraphStore
from cognite.neat.core.rules.models import TransformationRules
from cognite.neat.core.workflow.base import BaseWorkflow, FlowMessage


class GraphDbImportNeatWorkflow(BaseWorkflow):
    def __init__(self, name: str, client: CogniteClient):
        super().__init__(name, client, [])
        self.dataset_id: int = 0
        self.current_step: str = None
        self.source_graph: NeatGraphStore = None
        self.transformation_rules: TransformationRules = None
        self.stop_on_error = False
        self.extra_triplets = []

    def step_download_files_from_cdf(self, flow_msg: FlowMessage = None):
        # Download files from CDF
        logging.info("Downloading files from CDF")
        rdf_file_external_id = self.get_config_item("rdf_file_import.cdf_exteranl_id").value
        local_import_folder = self.get_config_item("rdf_file_import.shared_folder").value
        self.cdf_client.files.download(local_import_folder, external_id=rdf_file_external_id)

    def step_create_repository(self, flow_msg: FlowMessage = None):
        self.source_graph_api_url = self.get_config_item("source_rdf_store.api_root_url").value
        # Load rules from file or remote location
        logging.info("CREATEING REPO 2")
        repo_name = self.get_config_item("graphdb_repo_name").value
        req = {
            "id": repo_name,
            "params": {
                "queryTimeout": {"name": "queryTimeout", "label": "Query timeout (seconds)", "value": 30},
                "cacheSelectNodes": {"name": "cacheSelectNodes", "label": "Cache select nodes", "value": "true"},
                "rdfsSubClassReasoning": {
                    "name": "rdfsSubClassReasoning",
                    "label": "RDFS subClass reasoning",
                    "value": "true",
                },
                "validationEnabled": {
                    "name": "validationEnabled",
                    "label": "Enable the SHACL validation",
                    "value": "true",
                },
                "ftsStringLiteralsIndex": {
                    "name": "ftsStringLiteralsIndex",
                    "label": "FTS index for xsd:string literals",
                    "value": "default",
                },
                "shapesGraph": {
                    "name": "shapesGraph",
                    "label": "Named graphs for SHACL shapes",
                    "value": "http://rdf4j.org/schema/rdf4j#SHACLShapeGraph",
                },
                "parallelValidation": {
                    "name": "parallelValidation",
                    "label": "Run parallel validation",
                    "value": "true",
                },
                "title": {"name": "title", "label": "Repository description", "value": ""},
                "checkForInconsistencies": {
                    "name": "checkForInconsistencies",
                    "label": "Enable consistency checks",
                    "value": "false",
                },
                "performanceLogging": {
                    "name": "performanceLogging",
                    "label": "Log the execution time per shape",
                    "value": "false",
                },
                "disableSameAs": {"name": "disableSameAs", "label": "Disable owl:sameAs", "value": "true"},
                "ftsIrisIndex": {
                    "name": "ftsIrisIndex",
                    "label": "FTS index for full-text indexing of IRIs",
                    "value": "none",
                },
                "entityIndexSize": {"name": "entityIndexSize", "label": "Entity index size", "value": "10000000"},
                "dashDataShapes": {"name": "dashDataShapes", "label": "DASH data shapes extensions", "value": "true"},
                "queryLimitResults": {"name": "queryLimitResults", "label": "Limit query results", "value": 0},
                "throwQueryEvaluationExceptionOnTimeout": {
                    "name": "throwQueryEvaluationExceptionOnTimeout",
                    "label": "Throw exception on query timeout",
                    "value": "false",
                },
                "id": {"name": "id", "label": "Repository ID", "value": "repo-test"},
                "storageFolder": {"name": "storageFolder", "label": "Storage folder", "value": "storage"},
                "validationResultsLimitPerConstraint": {
                    "name": "validationResultsLimitPerConstraint",
                    "label": "Validation results limit per constraint",
                    "value": 1000,
                },
                "enablePredicateList": {
                    "name": "enablePredicateList",
                    "label": "Enable predicate list index",
                    "value": "true",
                },
                "transactionalValidationLimit": {
                    "name": "transactionalValidationLimit",
                    "label": "Transactional validation limit",
                    "value": "500000",
                },
                "ftsIndexes": {
                    "name": "ftsIndexes",
                    "label": "FTS indexes to build (comma delimited)",
                    "value": "default, iri",
                },
                "logValidationPlans": {
                    "name": "logValidationPlans",
                    "label": "Log the executed validation plans",
                    "value": "false",
                },
                "imports": {"name": "imports", "label": "Imported RDF files(';' delimited)", "value": ""},
                "inMemoryLiteralProperties": {
                    "name": "inMemoryLiteralProperties",
                    "label": "Cache literal language tags",
                    "value": "true",
                },
                "isShacl": {"name": "isShacl", "label": "Enable SHACL validation", "value": "false"},
                "ruleset": {"name": "ruleset", "label": "Ruleset", "value": "rdfsplus-optimized"},
                "readOnly": {"name": "readOnly", "label": "Read-only", "value": "false"},
                "enableFtsIndex": {
                    "name": "enableFtsIndex",
                    "label": "Enable full-text search (FTS) index",
                    "value": "false",
                },
                "enableLiteralIndex": {"name": "enableLiteralIndex", "label": "Enable literal index", "value": "true"},
                "enableContextIndex": {"name": "enableContextIndex", "label": "Enable context index", "value": "false"},
                "defaultNS": {
                    "name": "defaultNS",
                    "label": "Default namespaces for imports(';' delimited)",
                    "value": "",
                },
                "baseURL": {"name": "baseURL", "label": "Base URL", "value": "http://example.org/owlim#"},
                "logValidationViolations": {
                    "name": "logValidationViolations",
                    "label": "Log validation violations",
                    "value": "false",
                },
                "globalLogValidationExecution": {
                    "name": "globalLogValidationExecution",
                    "label": "Log every execution step of the SHACL validation",
                    "value": "false",
                },
                "entityIdSize": {"name": "entityIdSize", "label": "Entity ID size", "value": "32"},
                "repositoryType": {"name": "repositoryType", "label": "Repository type", "value": "file-repository"},
                "eclipseRdf4jShaclExtensions": {
                    "name": "eclipseRdf4jShaclExtensions",
                    "label": "RDF4J SHACL extensions",
                    "value": "true",
                },
                "validationResultsLimitTotal": {
                    "name": "validationResultsLimitTotal",
                    "label": "Validation results limit total",
                    "value": 1000000,
                },
            },
            "title": "",
            "type": "graphdb",
            "location": "",
        }
        r = requests.post(f"{self.source_graph_api_url}/rest/repositories", json=req)
        logging.info("Repository created with state: %s", r.text)
        if r.status_code > 202:
            if r.text.find("already exists") != -1:
                logging.info("Repository already exists")
                return FlowMessage(output_text="Repository already exists", output_data={})
            else:
                raise Exception(f"Repo creation failed , error from graphdb :{r.text}")

    def step_load_source_graph(self, flow_msg: FlowMessage = None):
        repo_name = self.get_config_item("graphdb_repo_name").value
        file_name = self.get_config_item("import_file_name").value
        import_prefix = self.get_config_item("import_prefix").value
        file_path = Path(file_name)
        if file_path.is_dir():
            pass
        req = {
            "importSettings": {
                "name": file_name,
                "status": "NONE",
                "message": "",
                "context": "",
                "replaceGraphs": [],
                "baseURI": import_prefix,
                "forceSerial": False,
                "type": "file",
                "format": None,
                "data": None,
                "timestamp": 1674660042160,
                "parserSettings": {
                    "preserveBNodeIds": False,
                    "failOnUnknownDataTypes": False,
                    "verifyDataTypeValues": False,
                    "normalizeDataTypeValues": False,
                    "failOnUnknownLanguageTags": False,
                    "verifyLanguageTags": True,
                    "normalizeLanguageTags": False,
                    "stopOnError": True,
                },
                "requestIdHeadersToForward": None,
            },
            "fileNames": [file_name],
        }
        r = requests.post(f"{self.source_graph_api_url}/rest/repositories/{repo_name}/import/server", json=req)
        logging.info(f"File import operation with code : {r.status_code} state: {r.text} ")
        if r.status_code > 202:
            raise Exception(f"The file import failed , error from graphdb :{r.text}")
        return FlowMessage(output_text="File import started successfully")

    def step_wait_for_import_complition(self, flow_msg: FlowMessage = None):
        repo_name = self.get_config_item("graphdb_repo_name").value
        for _ in range(1000):
            time.sleep(2)
            r = requests.get(f"{self.source_graph_api_url}/rest/repositories/{repo_name}/import/server")

            resp = r.json()
            logging.debug(f"Import status : {resp}")
            if resp[0]["status"] == "IMPORTING":
                continue
            elif resp[0]["status"] == "DONE":
                output_text = "File imported successfully . Message :" + resp[0]["message"]
                logging.info(output_text)
                return FlowMessage(output_text=output_text)
            else:
                raise Exception("Import failed with error :" + resp[0]["message"])
        raise Exception("Import operation timed out")

    def step_cleanup(self, flow_msg: FlowMessage = None):
        # TODO : cleanup
        self.categorized_assets = None
        self.categorized_relationships = None
