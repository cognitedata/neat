"""This script is used to test real data models from various sources.

It depends on the config file 'config_manual_test.yaml' which should be placed in the same folder as this script.

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
import traceback
from cognite.client import CogniteClient
from cognite.client.data_classes.data_modeling import DataModelId

from rich.panel import Panel

from cognite.neat.v0.core._data_model.models import PhysicalDataModel
from cognite.neat.v0.core._data_model.importers import DMSImporter
from cognite.neat.v0.core._data_model.exporters import DMSExporter
from pathlib import Path
from rich import print

from cognite.neat.v0.core._data_model.transformers import PhysicalToConceptual

TMP_FOLDER = Path(__file__).parent / 'tmp'
TMP_FOLDER.mkdir(exist_ok=True)

CONFIG_FILE = Path(__file__).parent / 'config_manual_test.yaml'


def main():
    total = 0
    failed = 0
    warning = 0
    success = 0
    failing_models = []
    for client, model_id in load_cases():
        total += 1
        print(Panel(f"Testing model: {model_id!r} from {client.config.project!r} CDF Project", expand=False))
        importer = DMSImporter.from_data_model_id(client, model_id)
        print("Successfully fetched model from CDF")
        rules, issues = importer.to_data_model()
        if issues.has_errors:
            print("[red]Errors[/red] found during conversion:")
            for issue in issues.errors:
                print(issue)
            print("Aborting")
            failing_models.append(model_id)
            failed += 1
            continue
        if not issues:
            print("[green]Successfully[/green] converted model to rules")
        else:
            print("Successfully converted model to rules with [yellow]issues[/yellow]")
            for issue in issues.warnings:
                print(issue)
            warning += 1
        assert isinstance(rules, PhysicalDataModel)
        try:
            information = PhysicalToConceptual().transform(rules)
        except Exception as e:
            print(f"[red]Failed[/red] to convert rules to information architect rules: {e}")
            print(Panel(traceback.format_exc(), expand=False))
            failing_models.append(model_id)
            failed += 1
            continue
        print("Successfully converted rules to information architect rules")
        exporter = DMSExporter()
        output_folder = TMP_FOLDER / f"{model_id.external_id}"
        if output_folder.exists():
            print("Output folder already exists, removing")
            shutil.rmtree(output_folder)
        output_folder.mkdir(exist_ok=True)
        try:
            exporter.export_to_file(information, output_folder)
        except Exception as e:
            print(f"[red]Failed[/red] to export information architect rules to folder: {e}")
            print(Panel(traceback.format_exc(), expand=False))
            failing_models.append(model_id)
            failed += 1
            continue
        print("Successfully exported information architect rules to file")
        success += 1
    print(Panel(f"Tested {total} Data Models\n[green]Success[/green]: {success}\n"
                f"[yellow]Warnings[/yellow]: {warning}\n"
                f"[red]Failed[/red]: {failed} {failing_models or ''}", expand=False))


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
            for model in client.data_modeling.data_models.list(limit=-1):
                yield client, model.as_id()
        else:
            for model in models:
                for model_version in client.data_modeling.data_models.retrieve((model['space'], model['externalId'])):
                    yield client, model_version.as_id()


if __name__ == '__main__':
    main()
