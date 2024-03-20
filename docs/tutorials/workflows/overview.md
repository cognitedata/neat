# Neat Workflows

Neat Workflow is concept that enables users to automate complex processes involving multiple steps and systems.
The workflow engine follows a modular, step-by-step process that can be customized to suit your specific data transformation needs. Each step in the workflow corresponds to a specific task, such as loading transformation rules, configuring graph stores, and loading the source graph.
Users can customize the workflow by adding or removing steps, or by modifying the parameters in each step to match their specific data requirements.

![Execution history](./artifacts/figs/wf-overview.gif)

## Terminology

- **Solution** - a package that contains a set of workflows, rules and other components that are used to solve a specific problem.
- **Workflow** - a set of steps that are executed in a specific order.
- **Step** - a single block of code (function) that is executed as part of a workflow.
- **Trigger** - a special type of step that can be used to trigger workflow execution.
- **Task** - is a special type of step that has provided implementation .
- **Flow message** - a message that is passed between steps. The message is a dictionary that contains information about the current state of the workflow.
- **Workflow manifest** - a YAML file that contains information about the workflow configuration , steps transitions , triggers and tasks cofiuration and other workflow related metadat.
- **Workflow context** - is local key-value store (scoped to a single workflow) that is used to store objects produced by steps. Objects stored in the context used for data sharing between steps via dependency injection.
- **Workflow Engine** - internal service that orchestrates steps execution.
- **Configurations** - a set of configurable parameters that are separated from the workflow logic and stored in manifest file (_workflow.yaml_). Configurations can be updated by a user via UI or API.
- **Transformation Rules** - Definition of data model and a set of rules that define how the data should be transformed from the source graph to the solution graph to the CDF resources. The rules are defined as Excel file.
- **Data modelling functions** - a collection of functions for data modelling. The functions are defined in a python module and provided by NEAT project.
- **Data transformation functions** - a collection of functions that define how the data should be transformed from the solution graph to the CDF resources. The functions are defined in a python module and provided by NEAT project.
- **Workflow Execution History** - a set of records that contain information about workflow execution history. The records are stored in the CDF and can be accessed via UI or API.

### Steps

Step is a block of isolated functionality that is packaged into python class that is inherited from `Step` base class. Steps are organized into workflows and executed in a specific order. Each step can have input and output parameters. Input parameters are passed to step from Flow context according to their data contract . Output parameters are stored in Flow context and can be used by other steps.

### Triggers

Trigger is a special type of step that can be used to trigger workflow execution.

Supported trigger types :

- `http_trigger` - HTTP trigger that can be used to trigger workflow execution via HTTP request.Also use by UI to trigger workflow execution.
- `time_trigger` - time trigger that can be used to trigger workflow execution on schedule.

`time_trigger` uses the schedule[https://pypi.org/project/schedule/] for workflow scheduling. To set up job schedules using `time_trigger`, enter natural language expressions within the `Time Interval` field of the corresponding step. Below are examples of supported natural language intervals:
- every day at 10:00
- every monday at 12:30:10
- every 60 minutes
- every 2 hours
- every 3 days
- every 30 seconds

### Tasks

Task is a special type of step that has provided implementation (no need to implement it in _workflow.py_) and can be used to perform some common tasks. Task are configured via `params` section in manifest file.

Supported task types :

- `start_workflow_task_step` - start another workflow. FlowMessage is passed to started workflow as input. The task supports synchronious and asynchronious execution.
- `wait_for_event` - the task pause workflow execution until event is received.

### Flow Message

FlowMessage is a special object that is passed from one step to another and it's captured in execution log.

```python
class FlowMessage(BaseModel):
    """A message that can be sent between steps in a workflow.It's the only parameter step takes as input."""

    payload: typing.Any = None  # The payload of the message
    headers: dict[str, str] = None  # The headers of the message
    output_text: str = None  # The output text of the step that is captured in the execution log
    error_text: str = None  # The error text of the step that is captured in the execution log
    next_step_ids: list[str] = None  # If set, the workflow will skip default route and go to the next step in the list
    step_execution_status: StepExecutionStatus = StepExecutionStatus.UNKNOWN  # The status of the step execution
```

`payload` property of FlowMessage is used to pass data between steps and automatically recorded in execution log.

FlowMessage can have `next_step_ids` property that defines which steps should be executed next. If `next_step_ids` is not set, next step will be executed based on execution graph defined in manifest.

FlowMessage can have `output_text` property that defines what should be logged in execution log and available in UI. If `output_text` is not set, method name will be used as output text. FlowMessage can have `error_text` property that defines error message that should be logged in execution log and available in UI in case of error.

### Static or dynamic execution graph

Execution graph defines which steps should be executed next.
By default, execution graph is static and defined in manifest file. It's possible to define dynamic execution graph by setting `next_step_ids` property of `FlowMessage`.

Example of dynamic routing :

```python
        if flow_msg.payload["action"] == "approve":
            return FlowMessage(next_step_ids=["cleanup"])
        else :
            return FlowMessage(next_step_ids=["step_45507"])
```


### Workflow start methods

NEAT supports 3 ways to start workflow execution : persistent non-blocking, persistent blocking, ephemeral mode. The mode is defined in manifest file via `workflow_start_method` property or via UI.

**Persistent non-blocking**

Only one running instance of workflow is allowed. If workflow execution is already running, new execution will dropped and error state returned to caller. Workflow execution is persisted in CDF and can be monitored via UI. All internal states preserved between executions.

![Persistent non-blocking](./artifacts/figs/wf-persistent-non-blocking.png)

**Persistent blocking(default)**

Only one running instance of the workflows is allowed. If workflow execution is already running, new execution will be queued and started later or timeout after max_wait_time. Workflow execution is persisted in CDF and can be monitored via UI.All internal states preserved between executions.

![Persistent blocking](./artifacts/figs/wf-persistent-blocking-mode.png)

**Ephemeral multi-instance mode**

Multiple running instances of the workflow are allowed. Each instance is a copy of main workflow class and are executed in parallel each in its own thread . Workflow execution is persisted in CDF but can't be monitored via UI.All internal states are lost between executions (ephemeral).

![Ephemeral mode](./artifacts/figs/wf-ephemeral-mode.png)

Configuring the mode in UI :

![Start mode UI](./artifacts/figs/wf-start-mode-ui.png)

### Workflow configuration parameters

Each Step can be configured independently , configuration parameters are defined in manifest file in `configs` section of each step. Configurations can be updated by a user via UI or API.
In addition to that, workflow can have system configuration parameters that have special meaning .
Supported system configuration parameters :

- `system.execution_reporting_type` - controls how workflow execution log should be reported to CDF . Supported values : `all_disabled`, `all_enabled`(default)


### Basic NEAT workflow definition

??? note "manifest.yaml example"

    ```yaml
    configs: []
    description: null
    implementation_module: null
    name: sheet2cdf
    steps:
    -   configs: null
        description: null
        enabled: true
        id: step_trigger
        label: Process trigger
        max_retries: 0
        method: null
        params:
            workflow_start_method: persistent_blocking
        retry_delay: 3
        stype: http_trigger
        system_component_id: null
        transition_to:
        - step_load_rules
        trigger: true
        ui_config:
            pos_x: 509
            pos_y: 93
    -   configs:
            file_name: sheet2cdf-transformation-rules.xlsx
            validate_rules: 'True'
            validation_report_file: rules_validation_report.txt
            validation_report_storage_dir: rules_validation_report
            version: ''
        description: null
        enabled: true
        id: step_load_rules
        label: Load rules from file
        max_retries: 0
        method: ExcelToRules
        params: {}
        retry_delay: 3
        stype: stdstep
        system_component_id: null
        transition_to:
        - step_reset_stores
        - step_configure_solution_store
        trigger: false
        ui_config:
            pos_x: 511
            pos_y: 165
    -   configs: {}
        description: null
        enabled: true
        id: step_load_rules_into_store
        label: Load rules as data into solution graph
        max_retries: 0
        method: InstancesFromRulesToSolutionGraph
        params: {}
        retry_delay: 3
        stype: stdstep
        system_component_id: null
        transition_to:
        - step_generate_assets
        trigger: false
        ui_config:
            pos_x: 507
            pos_y: 459
    -   configs: {}
        description: null
        enabled: true
        id: step_generate_assets
        label: Generate assets
        max_retries: 0
        method: GenerateCDFAssetsFromGraph
        params: {}
        retry_delay: 3
        stype: stdstep
        system_component_id: null
        transition_to:
        - step_generate_relations
        trigger: false
        ui_config:
            pos_x: 507
            pos_y: 556
    -   configs: {}
        description: null
        enabled: true
        id: step_generate_relations
        label: Generate relationships
        max_retries: 0
        method: GenerateCDFRelationshipsFromGraph
        params: {}
        retry_delay: 3
        stype: stdstep
        system_component_id: null
        transition_to:
        - step_upload_assets
        trigger: false
        ui_config:
            pos_x: 507
            pos_y: 632
    -   configs: {}
        description: null
        enabled: true
        id: step_upload_assets
        label: Upload assets
        max_retries: 0
        method: UploadCDFAssets
        params: {}
        retry_delay: 3
        stype: stdstep
        system_component_id: null
        transition_to:
        - step_upload_relations
        trigger: false
        ui_config:
            pos_x: 505
            pos_y: 711
    -   configs: {}
        description: null
        enabled: true
        id: step_upload_relations
        label: Upload relationships
        max_retries: 0
        method: UploadCDFRelationships
        params: {}
        retry_delay: 3
        stype: stdstep
        system_component_id: null
        transition_to: []
        trigger: false
        ui_config:
            pos_x: 506
            pos_y: 795
    -   configs: {}
        description: null
        enabled: true
        id: step_create_cdf_labels
        label: Create CDF labels
        max_retries: 0
        method: CreateCDFLabels
        params: {}
        retry_delay: 3
        stype: stdstep
        system_component_id: null
        transition_to:
        - step_load_rules_into_store
        trigger: false
        ui_config:
            pos_x: 508
            pos_y: 382
    -   configs:
            db_server_api_root_url: ''
            disk_store_dir: solution-graph-store-2
            graph_name: solution
            init_procedure: reset
            sparql_query_url: ''
            sparql_update_url: ''
            store_type: oxigraph
        description: null
        enabled: true
        id: step_configure_solution_store
        label: Configure solution graph store
        max_retries: 0
        method: ConfigureGraphStore
        params: {}
        retry_delay: 3
        stype: stdstep
        system_component_id: null
        transition_to:
        - step_create_cdf_labels
        trigger: false
        ui_config:
            pos_x: 509
            pos_y: 263
    system_components:
    -   description: null
        id: source_excel_sheet
        label: Transformation Rules
        transition_to:
        - excel2rdf_parser
        - cdf_classic_exporter
        ui_config:
            pos_x: 170
            pos_y: 10
    -   description: null
        id: excel2rdf_parser
        label: Excel to Graph Parser
        transition_to:
        - source_graph
        ui_config:
            pos_x: 0
            pos_y: 80
    -   description: null
        id: source_graph
        label: Source Graph
        transition_to:
        - in_memmory_store
        ui_config:
            pos_x: 0
            pos_y: 150
    -   description: null
        id: in_memmory_store
        label: In-Memory Graph Database
        transition_to:
        - cdf_classic_exporter
        ui_config:
            pos_x: 0
            pos_y: 220
    -   description: null
        id: cdf_classic_exporter
        label: CDF Classic Exporter
        transition_to:
        - cdf_classic
        ui_config:
            pos_x: 170
            pos_y: 330
    -   description: null
        id: cdf_classic
        label: CDF Classic (Asset,Relationships, Labels)
        transition_to: null
        ui_config:
            pos_x: 170
            pos_y: 400

    ```

### Versioning

Workflows and rule files are versioned automatically or manually. If version is not specified, NEAT will used hash of a file as version.

### Metrics and monitoring

Everything in measured in NEAT.
Metrics are exposed via prometheus compatible endpoint on http://<host:port>/metrics but also available in json format on http://<host:port>/api/metrics
The neat provides a set of default metrics and each Step can define custom metrics.

## Using the Workflow:

### Setup and Configuration:

To set up and configure your first NEAT workflow , follow these steps:

1. Create new workflow package or download existing workflow package from CDF or from GitHub workflow repository(not available yet)
2. Configure Steps in the manifest file or via UI to match your system requirements.
3. Execute the workflow using the command line , UI , via http trigger or time schedule trigger.
4. Monitor the progress of the workflow execution via UI or API.

### Packaging and automatic resource loading

Workflows are packaged as zip files and can be loaded from local file system or from CDF Files.

### Workflow sharing and remote storage

NEAT supports workflow sharing and storage via CDF.

### Execution history

NEAT stores detailed execution history in CDF and available via NEAT UI , REST API or directly in CDF.

![Execution history](./artifacts/figs/execution-history.gif)

### Data lineage

NEAT stores detailed data lineage in CDF. Produced resources can be tagged with unique execution id , workflow and rules file version.

### REST API

Open API docs : http://localhost:8000/docs

### Rules and conventions:

- Each workflow must reside in its own folder and folder name defines workflow name.
- Workflow folder must contain at least 1 file :
    - `workflow.yaml` - manifest and configurations
- FlowMessage is passed from one step to another and is captured in execution log.
- FlowMessage can have `next_step_ids` property that defines which steps should be executed next. If `next_step_ids` is not set, next step will be executed based on execution graph defined in manifest.
- FlowMessage can have `output_text` property that defines what should be logged in execution log and available in UI. If `output_text` is not set, method name will be used as output text.
- FlowMessage can have `error_text` property that defines error message that should be logged in execution log and available in UI in case of error.

Manifest file consist of 3 main sections:

- `configs` - workflow configuration parameters.
- `steps` - steps metadata.
- `system_components` - system or solutions components, is used for documentation purpose only.
- `description` - short description of the workflow.

### Troubleshooting:

In the event of errors or issues with the workflow engine, users should consult the log files generated by the engine for detailed error messages. The log files should provide information on the specific step in the workflow that caused the error, as well as any relevant error messages or stack traces.
Users can also consult the documentation for each step in the workflow for troubleshooting tips and best practices. In addition, the workflow engine may include built-in error handling and recovery mechanisms that can help mitigate errors and ensure that the workflow continues to execute even in the event of issues.
