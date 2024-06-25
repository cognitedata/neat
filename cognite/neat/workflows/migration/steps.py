from pathlib import Path

import yaml

# Migration mapping

# LoadTransformationRules to ImportExcelToRules
# InstancesFromRdfFileToSourceGraph to ExtractGraphFromRdfFile
# InstancesFromRulesToSolutionGraph to ExtractGraphFromRulesInstanceSheet
# GraphCapturingSheetToGraph to ExtractGraphFromGraphCapturingSheet
# GenerateMockGraph to ExtractGraphFromMockGraph
# InstancesFromJsonToGraph to ExtractGraphFromJsonFile
# InstancesFromAvevaPiAF to ExtractGraphFromAvevaPiAssetFramework
# DexpiToGraph to ExtractGraphFromDexpiFile
# GenerateCDFAssetsFromGraph to GenerateAssetsFromGraph
# GenerateCDFRelationshipsFromGraph to GenerateRelationshipsFromGraph
# GenerateCDFNodesAndEdgesFromGraph to GenerateNodesAndEdgesFromGraph
# UploadCDFAssets to LoadAssetsToCDF
# UploadCDFRelationships to LoadRelationshipsToCDF
# UploadCDFNodes to LoadNodesToCDF
# UploadCDFEdges to LoadEdgesToCDF
# CreateCDFLabels to LoadLabelsToCDF
# OpenApiToRules to `ImportOpenApiToRules
# ArbitraryJsonYamlToRules to ImportArbitraryJsonYamlToRules
# GraphToRules to ImportGraphToRules
# OntologyToRules to ImportOntologyToRules
# GraphQLSchemaFromRules to ExportGraphQLSchemaFromRules
# OntologyFromRules to ExportOntologyFromRules
# SHACLFromRules to ExportSHACLFromRules
# GraphCaptureSpreadsheetFromRules to ExportRulesToGraphCapturingSheet
# ExcelFromRules to ExportRulesToExcel

# Define a dictionary that maps old step names to new ones
step_rename_mapping = {
    "LoadTransformationRules": "ImportExcelToRules",
    "InstancesFromRdfFileToSourceGraph": "ExtractGraphFromRdfFile",
    "InstancesFromRulesToSolutionGraph": "ExtractGraphFromRulesInstanceSheet",
    "GraphCapturingSheetToGraph": "ExtractGraphFromGraphCapturingSheet",
    "GenerateMockGraph": "ExtractGraphFromMockGraph",
    "InstancesFromJsonToGraph": "ExtractGraphFromJsonFile",
    "InstancesFromAvevaPiAF": "ExtractGraphFromAvevaPiAssetFramework",
    "DexpiToGraph": "ExtractGraphFromDexpiFile",
    "GenerateCDFAssetsFromGraph": "GenerateAssetsFromGraph",
    "GenerateCDFRelationshipsFromGraph": "GenerateRelationshipsFromGraph",
    "GenerateCDFNodesAndEdgesFromGraph": "GenerateNodesAndEdgesFromGraph",
    "UploadCDFAssets": "LoadAssetsToCDF",
    "UploadCDFRelationships": "LoadRelationshipsToCDF",
    "UploadCDFNodes": "LoadNodesToCDF",
    "UploadCDFEdges": "LoadEdgesToCDF",
    "CreateCDFLabels": "LoadLabelsToCDF",
    "OpenApiToRules": "ImportOpenApiToRules",
    "ArbitraryJsonYamlToRules": "ImportArbitraryJsonYamlToRules",
    "GraphToRules": "ImportGraphToRules",
    "OntologyToRules": "ImportOntologyToRules",
    "GraphQLSchemaFromRules": "ExportGraphQLSchemaFromRules",
    "OntologyFromRules": "ExportOntologyFromRules",
    "SHACLFromRules": "ExportSHACLFromRules",
    "GraphCaptureSpreadsheetFromRules": "ExportRulesToGraphCapturingSheet",
    "ExcelFromRules": "ExportRulesToExcel",
}


def rename_workflow_steps(workflow_path: Path, dry_run: bool) -> str:
    # Load the YAML file
    data = yaml.safe_load(workflow_path.read_text())
    # Replace old step names with new ones
    for step in data["steps"]:
        if step["method"] in step_rename_mapping:
            print(f"Renaming step {step['method']} to {step_rename_mapping[step['method']]}")
            step["method"] = step_rename_mapping[step["method"]]

    # Save the updated YAML file
    with workflow_path.open("w") as file:
        yaml.safe_dump(data, file)
    return "ok"


def migrate_all_workflow_names(workflows_path: str, dry_run: bool) -> str:
    # Get all workflow files
    workflow_files = Path(workflows_path).rglob("workflow.yaml")
    # Migrate each workflow file
    for workflow_file in workflow_files:
        print(f"Migrating {workflow_file}")
        rename_workflow_steps(workflow_file, dry_run)
    return "ok"


if __name__ == "__main__":
    # print current directory
    print("The current directory is", Path.cwd())
    migrate_all_workflow_names("data/workflows", True)
