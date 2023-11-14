# Installation
`neat` is distributed as a Python package and as a docker image. These two distributions have different use cases:

* **Running in production**: `Docker`. This ensures that you have the correct version of all `neat` dependencies.
* **Experimenting**: `Python` or `Docker` whichever you are the most comfortable.
* **Developing custom workflows**: `Python` this enables you to import parts of `neat` to use in your workflow.

## Docker

**Prerequisites**: Installed Docker, see [docker.com](https://docs.docker.com/get-docker/) for installation instructions.

### Run latest `neat` version from Docker Hub

``` bash
docker run -p 8000:8000 --name neat cognite/neat:latest
```

**Run `neat` with mounted local file system**

Create a directory for storing `neat` data. This directory will be mounted into the container and used `neat` as local data store. This is useful if you want to persist data between restarts of the container or if you want access to the data outside of the container.

Example of creating a directory for storing `neat` data on Linux/Mac:

``` bash
mkdir /tmp/neat-data
```

Start container with volume mount :

``` bash
docker run -p 8000:8000 --name neat -v /tmp/neat-data:/app/data  cognite/neat:latest
```

Open `neat` in your browser: [http://localhost:8000](http://localhost:8000)


## Python package

**Prerequisites**: Installed Python 3.11, see [python.org](https://www.python.org/downloads/)

1. Create and enter directory for `neat` installation
1. Create a virtual environment:
2. Activate your virtual environment
3. Install `cognite-neat`
4. Setup configuration
5. Run `neat`

=== "Windows"

    ```
    mkdir neat && cd neat
    ```
    ```
    python -m venv venv
    ```
    ```
    venv\Scripts\activate.bat
    ```
    ```
    pip install cognite-neat
    ```
    Create `config.yaml`, see [Configuration](#configuration)
    ```
    neat
    ```

=== "Mac/Linux"

    ``` bash
    mkdir neat && cd neat
    ```
    ``` bash
    python -m venv venv
    ```
    ``` bash
    source venv/bin/activate
    ```
    ``` bash
    pip install cognite-neat
    ```
    Create `config.yaml`, see [Configuration](#configuration)
    ``` bash
    neat
    ```


# Configuration

`neat` has a global configuration which most importantly contains the credentials for connecting to CDF. In addition,
it also controls behavior such as logging, and storing and downloading of workflows.

The configuration can be provided as a file, `config.yaml`, or environmental variables. The recommended choice is
to use the configuration file.

**Prerequisite to creat a configuration**

1. Create a service principal in Azure AD.
2. Setup dataset(s) for `neat`.
3. Scope the access (capabilities in CDF) for these dataset(s).

=== "Create Service Principal"

    Follow <a href="https://docs.cognite.com/cdf/access/guides/add_service_principal" target="_blank">this guide</a> to
    create a service principal.

=== "Create dataset(s)"

    Follow <a href="https://docs.cognite.com/cdf/data_governance/guides/datasets/create_data_sets#step-1-create-a-data-set" target="_blank">this guide</a>
    to create a dataset.

    `neat` typically use multiple datasets. Each set of transformation rules typically has its own dataset, which used
    to store the CDF resources produced by the workflow using that transformation rules. This dataset is set in the
    metadata sheet in the spreadsheet.

    In addition, `neat` has a default dataset which is used for storing neat workflows and workflows runs. This
    dataset is set in the configuation under the key 'cdf_default_dataset_id'.

    It is recommended that you have one dataset for each of these uses in production, but for development and
    experiment purposes it is ok to use one dataset. You just have to ensure that this dataset has all
    the necessary capabilities.

=== "Add capabilities"

    Follow <a href="https://docs.cognite.com/cdf/access/guides/capabilities" target="_blank">this guide</a> to add
    capabilities.

    The requires capabilites depends on the workflow you are running. See for example, the [Sheet to CDF Graph Workflow](
    /tutorial/workflows/sheet2cdf.html).

    The default dataset needs the following capabilities

    | Capability Type | Action                                    | Scope    | Description                     |
    | --------------- | ----------------------------------------- |--------- |-------------------------------- |
    | Events          | `events:read`, `events:write`             | Datasets | Log workflow runs               |
    | Files           | `files:read`, `files:write`, `files:read` | Datasets | List, store, and read workflows |



## File `config.yaml`

When `neat` starts up it looks for `config.yaml` in the directory you start up. You can control the location
of this file with the environmental variable `NEAT_CONFIG_PATH`.

An example `config.yaml` file, which you can download [here](config.yaml)

```yaml
cdf_client:
    project: get-power-grid
    client_id: ca4b8f9c6-7d6e-4d7b-9cf3-6d4a32f8b7e1
    client_secret: Zy7!nM4cFp9sH3gR6tB8kL0oP7eU6wD5vQ4zN9yF
    client_name: neat-test-service
    base_url: https://az-power-no-northeurope.cognitedata.com
    scopes:
      - https://az-power-no-northeurope.cognitedata.com/.default
    token_url: https://login.microsoftonline.com/12a3b456-789c-0d1e-2f3a-4b56c78d9e0f/oauth2/v2.0/token
    timeout: 60
    max_workers: 3


workflows_store_type: file
cdf_default_dataset_id: 3931920688237191
workflow_downloader_filter:
    - tag:grid
log_level: DEBUG
```

## Environment
You can load the configuration from the environment instead of file by setting the environmental variable
`NEAT_CDF_PROJECT`. If this environment variable exists, then all the rest of the configuration

## Configuration Variables

| `yaml` Variable Name       | ENV variable name               | Description                                                    | Example                                                                                  |
|----------------------------|---------------------------------|----------------------------------------------------------------|------------------------------------------------------------------------------------------|
| cdf_client.project         | NEAT_CDF_PROJECT                | The CDF Project.                                               | get-power-grid                                                                           |
| cdf_client.client_id       | NEAT_CDF_CLIENT_ID              | The service principal client ID.                               | a4b8f9c6-7d6e-4d7b-9cf3-6d4a32f8b7e1                                                     |
| cdf_client.client_secret   | NEAT_CDF_CLIENT_SECRET          | The service principal client secret.                           | Zy7!nM4cFp9sH3gR6tB8kL0oP7eU6wD5vQ4zN9yF                                                 |
| cdf_client.client_name     | NEAT_CDF_CLIENT_NAME            | The service principal client name.                             | neat                                                                                     |
| cdf_client.base_url        | NEAT_CDF_BASE_URL               | The base URL of the CDF project                                | https://az-power-no-northeurope.cognitedata.com                                          |
| cdf_client.scopes          | NEAT_CDF_SCOPES                 | List of scopes                                                 | https://az-power-no-northeurope.cognitedata.com/.default                                 |
| cdf_client.token_url       | NEAT_CDF_TOKEN_URL              | Auth provider token URL                                        | https://login.microsoftonline.com/12a3b456-789c-0d1e-2f3a-4b56c78d9e0f/oauth2/v2.0/token |
| cdf_client.timeout         | NEAT_CDF_CLIENT_TIMEOUT         | The timeout for the CDF client (seconds).                      | 60                                                                                       |
| cdf_client.max_workers     | NEAT_CDF_CLIENT_MAX_WORKERS     | The maximum number of workers for the CDF client.              | 3                                                                                        |
| workflow_store_type        | NEAT_WORKFLOWS_STORE_TYPE       | How to store workflows, file, cdf, or url                      | file                                                                                     |
| workflow_store_path        | NEAT_DATA_PATH                  | Location for neat to store workflows, data, and configurations | /data                                                                                    |
| cdf_default_dataset_id     | NEAT_CDF_DEFAULT_DATASET_ID     | The identifier of the dataset ID.                              | 3931920688237191                                                                         |
| workflow_downloader_filter | NEAT_WORKFLOW_DOWNLOADER_FILTER | The filter used to download workflows                          | tag:grid, tag:power                                                                      |
| log_level                  | NEAT_LOG_LEVEL                  | Log level for neat, ERROR, WARNING, INFO, or DEBUG             | INFO                                                                                     |
| load_examples              | NEAT_LOAD_EXAMPLES              | If Trues , NEAT loads default examples during app startup      | True                                                                                     |
