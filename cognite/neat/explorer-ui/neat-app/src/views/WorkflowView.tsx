import { useCallback, useRef } from 'react';
import ReactFlow, {
  MiniMap,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Node,
  updateEdge,
  Panel,
  NodeChange,
  EdgeChange,
} from 'reactflow';
// 👇 you need to import the reactflow styles
import 'reactflow/dist/style.css';
import Button from '@mui/material/Button';
import { useState, useEffect } from 'react';
import Stack from '@mui/material/Stack';
import { styled } from '@mui/material/styles';
import Paper from '@mui/material/Paper';
import { UIConfig, WorkflowDefinition, WorkflowStepDefinition, WorkflowSystemComponent} from 'types/WorkflowTypes';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select, { SelectChangeEvent } from '@mui/material/Select';
import { Box } from '@mui/system';
import MenuItem from '@mui/material/MenuItem';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import ToggleButton from '@mui/material/ToggleButton';
import { getNeatApiRootUrl, getSelectedWorkflowName, setSelectedWorkflowName } from 'components/Utils';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import TextField from '@mui/material/TextField';
import { Checkbox, FormControlLabel, FormGroup } from '@mui/material';
import CdfPublisher from 'components/CdfPublisher';
import CdfDownloader from 'components/CdfDownloader';
import WorkflowExecutionReport from 'components/WorkflowExecutionReport';
import ConfigView from './ConfigView';
import TransformationTable from './TransformationView';
import QDataTable from './ExplorerView';
import Editor, { DiffEditor, useMonaco, loader } from '@monaco-editor/react';
import OverviewComponentEditorDialog from 'components/OverviewComponentEditorDialog';

export interface ExecutionLog {
  id: string;
  state: string;
  elapsed_time: number;
  timestamp: string;
  error: string;
  output_text: string;
  data: any;
}

export interface WorkflowStats {
  state: string;
  elapsed_time: number;
  last_error: string;
  execution_log: ExecutionLog[];
}

const Item = styled(Paper)(({ theme }) => ({
  backgroundColor: theme.palette.mode === 'dark' ? '#1A2027' : '#fff',
  ...theme.typography.body2,
  padding: theme.spacing(1),
  textAlign: 'left',
  color: theme.palette.text.secondary,
}));



export default function WorkflowView() {
  const neatApiRootUrl = getNeatApiRootUrl();
  const edgeUpdateSuccessful = useRef(true);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [workflowStats, setWorkflowStats] = useState<WorkflowStats>();
  const [timerInterval, setTimerInterval] = useState(null);
  const [workflowDefinitions, setWorkflowDefinitions] = useState<WorkflowDefinition>();
  const [selectedWorkflow, setSelectedWorkflow] = useState<string>(getSelectedWorkflowName());
  const [listOfWorkflows, setListOfWorkflows] = useState<string[]>([]);
  const [viewType, setViewType] = useState<string>("system");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [openOverviewComponentEditorDialog, setOpenOverviewComponentEditorDialog] = useState(false);
  const [selectedStep, setSelectedStep] = useState<WorkflowStepDefinition>();
  const [selectedComponent, setSelectedComponent] = useState<WorkflowSystemComponent>();
  const [fileContent, setFileContent] = useState('');


  useEffect(() => {
    loadListOfWorkflows();
    loadWorkflowDefinitions(getSelectedWorkflowName());
    startStatePolling();
  
  }, []);

  const fetchFileContent = async () => {
    try {
      var myHeaders = new Headers();
      myHeaders.append('pragma', 'no-cache');
      myHeaders.append('cache-control', 'no-cache');
      const response = await fetch(neatApiRootUrl + '/data/workflows/' + selectedWorkflow + '/workflow.py', { method: "get", headers: myHeaders });
      const content = await response.text();
      setFileContent(content);
    } catch (error) {
      console.error('Error fetching file:', error);
    }
  };

  useEffect(() => {
    console.log("workflow definition changed")
    syncWorkflowDefToNodesAndEdges(viewType);
  }, [workflowDefinitions]);

  // useEffect(() => {
  //   console.log("node or edge changed")
  //   syncNodesAndEdgesToWorkflowDef();
  // }, [nodes, edges]);

  const startStatePolling = () => {
    if (!timerInterval) {
      let timerInterval = setInterval(() => {
        loadWorkflowStats();
      }, 2000);
      setTimerInterval(timerInterval);
    }

  }

  const stopStatePolling = () => {
    clearInterval(timerInterval);
    // timerInterval = null;
  }

  const loadListOfWorkflows = () => {
    const url = neatApiRootUrl + "/api/workflow/workflows";
    fetch(url).then((response) => response.json()).then((data) => {
      setListOfWorkflows(data.workflows);
    }).catch((error) => {
      console.error('Error:', error);
    }).finally(() => { });
  }

  const loadWorkflowDefinitions = (workflowName: string = "") => {
    if (workflowName == "")
      workflowName = selectedWorkflow;
    const url = neatApiRootUrl + "/api/workflow/workflow-definition/" + workflowName;
    fetch(url).then((response) => response.json()).then((data) => {
      const workflows = WorkflowDefinition.fromJSON(data.definition);
      setWorkflowDefinitions(workflows);
      // loadWorkflowStats(workflowName);
  }).catch ((error) => {
    console.error('Error:', error);
  }).finally(() => { });
}

const filterStats = (stats: WorkflowStats) => {
  console.log("loadWorkflowStats")
  console.dir(stats)
  // detelete all log RUNNING entries that have both RUNNING and COMPLETED entries for the same step
  if (stats.execution_log == null)
    return stats;

  const filteredLog = stats.execution_log!.filter((log, index) => {
    if (log.state == "STARTED") {
      const nextLog = stats.execution_log[index + 1];
      if (nextLog && nextLog.state == "COMPLETED" && nextLog.id == log.id)
        return false;
    }
    return true;
  })
  stats.execution_log = filteredLog;
  return stats;
}

const loadWorkflowStats = (workflowName: string = "") => {
  if (workflowName == "")
    workflowName = selectedWorkflow;
  const url = neatApiRootUrl + "/api/workflow/stats/" + workflowName;
  fetch(url).then((response) => response.json()).then((data) => {

    // const filteredStats = filterStats(data);
    setWorkflowStats(data);
    if (data.state == "RUNNING") {
      // startStatePolling();
    } else if (data.state == "COMPLETED" || data.state == "FAILED") {
      // stopStatePolling();
    }

  }).catch((error) => {
    console.error('Error:', error);
  })
}

const startWorkflow = () => {
  const url = neatApiRootUrl + "/api/workflow/start";
  const params = { name: selectedWorkflow, config: "", start_step: "" };
  fetch(url, {
    method: "post", body: JSON.stringify(params), headers: {
      'Content-Type': 'application/json;charset=utf-8'
    }
  }).then((response) => response.json()).then((data) => {
    console.dir(data)
    setWorkflowStats(data);
    startStatePolling();
    loadWorkflowStats();
  }).catch((error) => {
    console.error('Error:', error);
  })
}


const saveWorkflow = () => {
  console.dir(nodes);
  syncNodesAndEdgesToWorkflowDef();
  let wdef = workflowDefinitions;
  console.dir(wdef);
  const url = neatApiRootUrl + "/api/workflow/workflow-definition/" + selectedWorkflow;
  fetch(url, {
    method: "post", body: wdef.serializeToJson(), headers: {
      'Content-Type': 'application/json;charset=utf-8'
    }
  }).then((response) => response.json()).then((data) => {
    console.dir(data)
  }
  ).catch((error) => {
    console.error('Error:', error);
  })
};

const syncNodesAndEdgesToWorkflowDef = () => {
  if (workflowDefinitions) {
    workflowDefinitions.updatePositions(nodes);
    if (viewType == "system")
      workflowDefinitions.updateSystemComponentTransitions(edges);
    else
      workflowDefinitions.updateStepTransitions(edges);
  } else {
    console.error("workflowDefinitions is null");
  }

}

const syncWorkflowDefToNodesAndEdges = (viewType:string) => {
  if (!workflowDefinitions)
    return;
  switch (viewType) {
    case 'steps':
      setNodes(workflowDefinitions.convertStepsToNodes());
      setEdges(workflowDefinitions.convertStepsToEdges());
      break;
    case 'system':
      setNodes(workflowDefinitions.convertSystemComponentsToNodes());
      setEdges(workflowDefinitions.convertSystemComponentsToEdges());
  }
}


const reloadWorkflows = () => {
  const url = neatApiRootUrl + "/api/workflow/reload-workflows";
  fetch(url, {
    method: "post", body: "", headers: {
      'Content-Type': 'application/json;charset=utf-8'
    }
  }).then((response) => response.json()).then((data) => {
    loadWorkflowDefinitions();
  }
  ).catch((error) => {
    console.error('Error:', error);
  })
};

const handleWorkflowSelectorChange = (event: SelectChangeEvent) => {
  console.dir("Workflow changed to :" + event.target.value);
  setSelectedWorkflowName(event.target.value);
  setSelectedWorkflow(event.target.value);
  loadWorkflowDefinitions(event.target.value);
  setViewType("system");
  syncWorkflowDefToNodesAndEdges("system");
};

const handleViewTypeChange = (
  event: React.MouseEvent<HTMLElement>,
  newViewType: string,
) => {

  setViewType(newViewType);
  syncWorkflowDefToNodesAndEdges(newViewType);
  if (viewType == "src") {
    fetchFileContent();
  }
};


const onConnect = useCallback((params) => {
  console.log('onConnect')
  setEdges((eds) => addEdge(params, eds))
  syncNodesAndEdgesToWorkflowDef();
}, [setEdges]);

const onEdgeUpdateStart = useCallback(() => {
  console.log('onEdgeUpdateStart')
  edgeUpdateSuccessful.current = false;
}, []);

const onEdgeUpdate = useCallback((oldEdge, newConnection) => {
  console.log('onEdgeUpdate')
  edgeUpdateSuccessful.current = true;
  setEdges((els) => updateEdge(oldEdge, newConnection, els));
}, [setEdges]);

const onEdgeUpdateEnd = useCallback((_, edge) => {
  console.log('onEdgeUpdateEnd')
  if (!edgeUpdateSuccessful.current) {
    setEdges((eds) => eds.filter((e) => e.id !== edge.id));
    syncNodesAndEdgesToWorkflowDef();
  }

  edgeUpdateSuccessful.current = true;
}, [setEdges]);

const onNodeClick = useCallback((event, node) => {
  console.log('onNodeClick')
  console.dir(node);
  handleDialogClickOpen(node.id, viewType);
}, [workflowDefinitions, viewType]);

const onAddStep = (() => {
  console.log('onAddStep')
  const ui_config = new UIConfig();
  ui_config.pos_x = 100;
  ui_config.pos_y = 100;
  if (viewType == "steps") {
    const step = new WorkflowStepDefinition();
    step.id = "step_" + Math.floor(Math.random() * 1000000);
    step.label = "New step";
    step.ui_config = ui_config;
    workflowDefinitions.steps.push(step);
  } else {
    const systemComponent = new WorkflowSystemComponent();
    systemComponent.id = "system_comp_" + Math.floor(Math.random() * 1000000);
    systemComponent.label = "New component";
    systemComponent.ui_config = ui_config;
    workflowDefinitions.system_components.push(systemComponent);
  }
  syncWorkflowDefToNodesAndEdges(viewType);
});

const handleDialogClickOpen = (id: string, viewType: string) => {
  console.log(viewType);
  if (viewType == "steps") {
    setSelectedStep(workflowDefinitions.getStepById(id));
    setDialogOpen(true);
  } else {
    setSelectedComponent(workflowDefinitions.getSystemComponentById(id));
    setOpenOverviewComponentEditorDialog(true);
  }
};

const handleDialogClose = () => {
  setDialogOpen(false);
  syncWorkflowDefToNodesAndEdges(viewType);
};

const handleDialogCloseDelete = () => {
  workflowDefinitions.deleteStep(selectedStep.id);
  setDialogOpen(false);
  syncWorkflowDefToNodesAndEdges(viewType);
};

const handleStepConfigChange = (name: string, value: any) => {
  console.log('handleStepConfigChange')
  console.dir(selectedStep);

  if (selectedStep) {
    if (!selectedStep.params) {
      selectedStep.params = {}
    }
    if (name == "stype") {
      switch (value) {
        case "time_trigger":
          selectedStep.params = { "interval": "every 60 minutes" }
          break;
        case "start_workflow_task_step":
          selectedStep.params = { "workflow_name": "", "sync": "false" }
          break;
      }
      selectedStep["stype"] = value;
    } else {
      switch (name) {
        case "time-interval":
          selectedStep.params["interval"] = value;
          break;
        case "workflow_name":
          selectedStep.params["workflow_name"] = value;
          break;
        case "workflow_sync_run_flag":
          value = "false"
          if (value) {
            value = "true"
          }
          selectedStep.params["sync"] = value;
          break;
        default:
          selectedStep[name] = value;
      }
    }
    console.log("rendering view")
    syncWorkflowDefToNodesAndEdges(viewType);
  }
}

const onDownloadSuccess = (fileName: string, hash: string) => {
  console.log("onDownloadSuccess", fileName, hash)
  reloadWorkflows();
}
const solutionComponentEditorDialogHandler = (component: WorkflowSystemComponent,action: string) => {
  console.log("OverviewComponentEditorDialogHandler")
  console.dir(component)
  switch (action) {
    case "save":
      workflowDefinitions.updateSystemComponent(selectedComponent.id, component);
      setSelectedComponent(component);
      syncWorkflowDefToNodesAndEdges(viewType);
      break;
    case "delete":
      workflowDefinitions.deleteSystemComponent(component.id);
      syncWorkflowDefToNodesAndEdges(viewType);
      break;
  }
  setOpenOverviewComponentEditorDialog(false);
}

const onNodesChangeN = useCallback((nodeChanges: NodeChange[]) => {
  // console.log('onNodesChange')
  // console.dir(nodeChanges);
  onNodesChange(nodeChanges);
  syncNodesAndEdgesToWorkflowDef();
}, [workflowDefinitions,nodes,edges]);

const onEdgesChangeN = useCallback((edgeChanges: EdgeChange[]) => {
  console.log('onEdgesChange')
  console.dir(edgeChanges);
  onEdgesChange(edgeChanges);
  syncNodesAndEdgesToWorkflowDef();
}, [workflowDefinitions,nodes,edges]);

return (
  <div style={{ height: '85vh', width: '97vw' }}>
    <Box>
      <FormControl sx={{ width: 300, marginBottom: 2 }}>
        <InputLabel id="workflowSelectorLabel">Workflow selector</InputLabel>
        <Select
          labelId="workflowSelectorLabel"
          id="workflowSelector"
          value={selectedWorkflow}
          size='small'
          label="Query template"
          onChange={handleWorkflowSelectorChange}
        >
          {
            listOfWorkflows && listOfWorkflows.map((item, i) => (
              <MenuItem value={item} key={item}>{item} </MenuItem>
            ))
          }
        </Select>
      </FormControl>
      <ToggleButtonGroup
        color="primary"
        value={viewType}
        exclusive
        size='small'
        sx={{ marginLeft: 2 }}
        onChange={handleViewTypeChange}
        aria-label="View type"
      >
        <ToggleButton value="system">Solution overview</ToggleButton>
        <ToggleButton value="steps">Steps</ToggleButton>
        <ToggleButton value="configurations">Configurations</ToggleButton>
        <ToggleButton value="src">Source code</ToggleButton>
        <ToggleButton value="transformations">Transformation rules</ToggleButton>
        <ToggleButton value="data_explorer">Data explorer</ToggleButton>

      </ToggleButtonGroup>
      <Dialog open={dialogOpen} onClose={handleDialogClose}>
        <DialogTitle>Step configurator</DialogTitle>
        <DialogContent>
          <FormControl sx={{ width: 300 }} >
            <TextField sx={{ marginTop: 1 }} id="step-config-id" fullWidth label="Step id" size='small' variant="outlined" value={selectedStep?.id} onChange={(event) => { handleStepConfigChange("id", event.target.value) }} />
            <TextField sx={{ marginTop: 1 }} id="step-config-label" fullWidth label="Label" size='small' variant="outlined" value={selectedStep?.label} onChange={(event) => { handleStepConfigChange("label", event.target.value) }} />
            <Select sx={{ marginTop: 1 }}
              id="step-config-stype"
              value={selectedStep?.stype}
              label="Step type"
              size='small'
              variant="outlined"
              onChange={(event) => { handleStepConfigChange("stype", event.target.value) }}
            >
              <MenuItem value="pystep">Python function</MenuItem>
              <MenuItem value="http_trigger">HTTP trigger</MenuItem>
              <MenuItem value="time_trigger">Time trigger</MenuItem>
              <MenuItem value="wait_for_event">Wait for event</MenuItem>
              <MenuItem value="start_workflow_task_step">Start workflow</MenuItem>
            </Select>

            <TextField sx={{ marginTop: 1 }} id="step-config-descr" fullWidth label="Description" size='small' variant="outlined" value={selectedStep?.description} onChange={(event) => { handleStepConfigChange("description", event.target.value) }} />
            {(selectedStep?.stype == "time_trigger") && (
              <TextField sx={{ marginTop: 1 }} id="step-config-time-config" fullWidth label="Time interval" size='small' variant="outlined" value={selectedStep?.params["interval"]} onChange={(event) => { handleStepConfigChange("time-interval", event.target.value) }} />
            )}
            {(selectedStep?.stype == "start_workflow_task_step") && (
              <TextField sx={{ marginTop: 1 }} id="step-start_workflow_task_step" fullWidth label="Name of the workflow" size='small' variant="outlined" value={selectedStep?.params["workflow_name"]} onChange={(event) => { handleStepConfigChange("workflow_name", event.target.value) }} />
            )}
            {(selectedStep?.stype == "start_workflow_task_step") && (
              <FormControlLabel control={<Checkbox checked={selectedStep?.params["sync"] == "true"} onChange={(event) => { handleStepConfigChange("workflow_sync_run_flag", event.target.checked) }} />} label="Synchronous execution" />
            )}
            <FormControlLabel control={<Checkbox checked={selectedStep?.enabled} onChange={(event) => { handleStepConfigChange("enabled", event.target.checked) }} />} label="Is enabled" />
            <FormControlLabel control={<Checkbox checked={selectedStep?.trigger} onChange={(event) => { handleStepConfigChange("trigger", event.target.checked) }} />} label="Is trigger" />
          </FormControl>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleDialogClose}>Cancel</Button>
          <Button onClick={handleDialogClose}>Save</Button>
          <Button onClick={handleDialogCloseDelete}>Delete</Button>
        </DialogActions>
      </Dialog>
    </Box>
    {(viewType == "system" || viewType == "steps") && (
      <Stack direction="row" spacing={1} justifyContent="left"
        alignItems="left">
        <Item>
          <OverviewComponentEditorDialog open={openOverviewComponentEditorDialog} component={selectedComponent} onClose={solutionComponentEditorDialogHandler} />
          <div style={{ height: '75vh', width: '70vw' }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodeClick={onNodeClick}
              onNodesChange={onNodesChangeN}
              onEdgesChange={onEdgesChangeN}
              onEdgeUpdate={onEdgeUpdate}
              onEdgeUpdateStart={onEdgeUpdateStart}
              onEdgeUpdateEnd={onEdgeUpdateEnd}
              onConnect={onConnect}
            >
              <MiniMap />
              <Controls />
              <Background />
              <Panel position="bottom-center"><Button variant="outlined" onClick={onAddStep}>Add step</Button></Panel>
            </ReactFlow>

            <Button variant="contained" onClick={startWorkflow} sx={{ marginTop: 2, marginRight: 1 }}>Start workflow</Button>
            <Button variant="contained" onClick={saveWorkflow} sx={{ marginTop: 2, marginRight: 1 }}>Save workflow</Button>
            <Button variant="contained" onClick={reloadWorkflows} sx={{ marginTop: 2, marginRight: 1 }} >Reload local workflows</Button>
            <Box sx={{ marginTop: 1, marginBottom: 1 }}>
              <CdfPublisher type="workflow" />
              <CdfDownloader type="workflow-package" onDownloadSuccess={onDownloadSuccess} />
            </Box>
          </div>

        </Item>
        <Item >
          <WorkflowExecutionReport report={workflowStats} />
        </Item>
      </Stack>
    )}
    {viewType == "configurations" && (
      <ConfigView></ConfigView>
    )}
    {viewType == "transformations" && (
      <TransformationTable />
    )}
    {viewType == "data_explorer" && (
      <QDataTable />
    )}
    {viewType == "src" && (
      <Editor height="90vh" defaultLanguage="python" value={fileContent} />
    )}

  </div>


);
}
