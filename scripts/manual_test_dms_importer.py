"""This scrips is used to test real data models from various sources.

It depends on the config file 'manual_test_config.yaml' which should be placed in the same folder as this script.

```yaml
- credentials:
    loginFlow: interactive
    project: --
    cdfCluster: --
    tenantId: --
    clientId: --
  models:
    - space: <model_space>
      externalId: <model externalId>
- credentials:
    loginFlow: client_credentials
    project: --
    cdfCluster: --
    tenantId: --
    clientId: --
    clientSecret: --
  models: all # Will load all models that the client can access.
```
"""
import shutil
from collections.abc import Iterable

import yaml
from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import DataModelId
from typing import cast

from rich.panel import Panel

from cognite.neat.rules.models import DMSRules
from cognite.neat.rules.importers import DMSImporter
from cognite.neat.rules.exporters import DMSExporter
from pathlib import Path
from rich import print

TMP_FOLDER = Path(__file__).parent / 'tmp'
TMP_FOLDER.mkdir(exist_ok=True)

CONFIG_FILE = Path(__file__).parent / 'manual_test_config.yaml'


def main():
    total = 0
    failed = 0
    warning = 0
    success = 0
    for client, model_id in load_cases():
        total += 1
        print(Panel(f"Testing model: {model_id} from {client.config.project}"))
        importer = DMSImporter.from_data_model_id(client, model_id)
        print("Successfully fetched model from CDF")
        rules, issues = importer.to_rules()
        if issues.has_errors:
            print("[red]Errors[/red] found during conversion:")
            for issue in issues.errors:
                print(issue.message())
            print("Aborting")
            failed += 1
            continue
        if not issues:
            print("[green]Successfully[/green] converted model to rules")
        else:
            print("Successfully converted model to rules with [yellow]issues[/yellow]")
            for issue in issues.warnings:
                print(issue)
            warning += 1
        assert isinstance(rules, DMSRules)
        information = rules.as_information_architect_rules()
        print("Successfully converted rules to information architect rules")
        exporter = DMSExporter()
        output_folder = TMP_FOLDER / f"{model_id.external_id}"
        if output_folder.exists():
            print("Output folder already exists, removing")
            shutil.rmtree(output_folder)
        output_folder.mkdir(exist_ok=True)
        exporter.export_to_file(information, output_folder)
        print("Successfully exported information architect rules to file")
        success += 1
    print(Panel(f"Total: {total}, Success: {success}, Warnings: {warning}, Failed: {failed} Data Models"))

def load_cases() -> Iterable[tuple[CogniteClient, DataModelId]]:
    config_file = yaml.safe_load(CONFIG_FILE.read_text())
    if not isinstance(config_file, list):
        config_file = [config_file]
    for entry in config_file:
        credentials = entry['credentials']
        project, cluster, tenant_id, client_id = credentials['project'], credentials['cdfCluster'], credentials['tenantId'], credentials['clientId']
        login_flow = credentials['loginFlow'].replace("_", "").casefold()
        if login_flow == "interactive":
            client = CogniteClient.default_oauth_interactive(project=project, cdf_cluster=cluster, tenant_id=tenant_id, client_id=client_id)
        elif login_flow == "clientcredentials":
            client_secret = credentials['clientSecret']
            client = CogniteClient.default_oauth_client_credentials(project=project, cdf_cluster=cluster, tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
        else:
            raise ValueError(f"Unknown login flow: {login_flow}")
        models = entry['models']
        if models == "all":
            for model in client.data_modeling.data_models.list():
                yield client, model.as_id()
        else:
            for model in models:
                yield client, DataModelId(model['space'], model['externalId'])


if __name__ == '__main__':
    main()
