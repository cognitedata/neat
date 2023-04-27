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
} from 'reactflow';
// 👇 you need to import the reactflow styles
import 'reactflow/dist/style.css';
import Button from '@mui/material/Button';
import { useState, useEffect } from 'react';
import Timeline from '@mui/lab/Timeline';
import TimelineItem, { timelineItemClasses } from '@mui/lab/TimelineItem';
import TimelineSeparator from '@mui/lab/TimelineSeparator';
import TimelineConnector from '@mui/lab/TimelineConnector';
import TimelineContent from '@mui/lab/TimelineContent';
import TimelineDot from '@mui/lab/TimelineDot';
import Stack from '@mui/material/Stack';
import { styled } from '@mui/material/styles';
import Paper from '@mui/material/Paper';
import CircularProgress from '@mui/material/CircularProgress';
import { UIConfig, WorkflowDefinition, WorkflowStepDefinition } from 'types/WorkflowTypes';
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
import DialogContentText from '@mui/material/DialogContentText';
import DialogActions from '@mui/material/DialogActions';
import TextField from '@mui/material/TextField';
import { Checkbox, FormControlLabel, FormGroup } from '@mui/material';
import CdfPublisher from 'components/CdfPublisher';
import CdfDownloader from 'components/CdfDownloader';
import NJsonViewer from 'components/JsonViewer';
import WorkflowExecutionReport from 'components/WorkflowExecutionReport';


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
  let timerInterval = null;
  const [workflowDefinitions, setWorkflowDefinitions] = useState<WorkflowDefinition>();
  const [selectedWorkflow, setSelectedWorkflow] = useState<string>(getSelectedWorkflowName());
  const [listOfWorkflows, setListOfWorkflows] = useState<string[]>([]);
  const [viewType, setViewType] = useState<string>("system");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedStep, setSelectedStep] = useState<WorkflowStepDefinition>();

  useEffect(() => {
    loadConfigs();
    loadListOfWorkflows();
    loadWorkflowDefinitions(getSelectedWorkflowName());
  }, []);

  useEffect(() => {
    renderView(viewType);
  }, [workflowDefinitions]);

  const startStatePolling = () => {
    if (!timerInterval) {
      timerInterval = setInterval(() => {
        loadWorkflowStats();
      }, 2000);
    }

  }

  const stopStatePolling = () => {
    clearInterval(timerInterval);
    timerInterval = null;
  }


  const loadConfigs = () => {
    const url = neatApiRootUrl+"/api/configs";
    fetch(url).then((response) => response.json()).then((data) => {
      console.dir(data)

    }).catch((error) => {
      console.error('Error:', error);
    }).finally(() => { });
  }

  const loadListOfWorkflows = () => {
    const url = neatApiRootUrl+"/api/workflow/workflows";
    fetch(url).then((response) => response.json()).then((data) => {
      setListOfWorkflows(data.workflows);
    }).catch((error) => {
      console.error('Error:', error);
    }).finally(() => { });
  }

  const loadWorkflowDefinitions = (workflowName: string = "") => {
    if (workflowName == "")
      workflowName = selectedWorkflow;
    const url = neatApiRootUrl+"/api/workflow/workflow-definition/" + workflowName;
    fetch(url).then((response) => response.json()).then((data) => {
      const workflows = WorkflowDefinition.fromJSON(data.definition);
      console.dir(workflows);
      setWorkflowDefinitions(workflows);
      loadWorkflowStats(workflowName);
    }).catch((error) => {
      console.error('Error:', error);
    }).finally(() => { });
  }

  const filterStats = (stats: WorkflowStats) => {
    console.log("loadWorkflowStats")
    console.dir(stats)
    // detelete all log RUNNING entries that have both RUNNING and COMPLETED entries for the same step
    if (stats.execution_log == null )
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
    const url = neatApiRootUrl+"/api/workflow/stats/" + workflowName;
    fetch(url).then((response) => response.json()).then((data) => {

      // const filteredStats = filterStats(data);
      setWorkflowStats(data);
      if (data.state == "RUNNING") {
        startStatePolling();
      } else if (data.state == "COMPLETED" || data.state == "FAILED")
        stopStatePolling();

    }).catch((error) => {
      console.error('Error:', error);
    })
  }

  const startWorkflow = () => {
    const url = neatApiRootUrl+"/api/workflow/start";
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
    let wdef = workflowDefinitions;
    wdef.updatePositions(nodes);
    wdef.updateStepTransitions(edges);
    console.dir(wdef);
    const url = neatApiRootUrl+"/api/workflow/workflow-definition/" + selectedWorkflow;
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

  const reloadWorkflows = () => {
    const url = neatApiRootUrl+"/api/workflow/reload-workflows";
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
    console.dir(event.target.value);
    setSelectedWorkflowName(event.target.value);
    setSelectedWorkflow(event.target.value);
    loadWorkflowDefinitions(event.target.value);

  };

  const handleViewTypeChange = (
    event: React.MouseEvent<HTMLElement>,
    viewType: string,
  ) => {
    setViewType(viewType);
    renderView(viewType);
  };

  const renderView = (viewType: string) => {
    if (!workflowDefinitions)
      return;
    switch (viewType) {
      case 'steps':
        setNodes(workflowDefinitions.convertStepsToNodes());
        setEdges(workflowDefinitions.convertStepsToEdges());
        break;
      case 'system':
        setNodes(workflowDefinitions.convertGroupsToNodes());
        setEdges(workflowDefinitions.convertGroupsToEdges());

    }
  }
  const onConnect = useCallback((params) => {
    console.log('onConnect')
    setEdges((eds) => addEdge(params, eds))
  }, [setEdges]);

  const onEdgeUpdateStart = useCallback(() => {
    console.log('onEdgeUpdateStart')
    edgeUpdateSuccessful.current = false;
  }, []);

  const onEdgeUpdate = useCallback((oldEdge, newConnection) => {
    console.log('onEdgeUpdate')
    edgeUpdateSuccessful.current = true;
    setEdges((els) => updateEdge(oldEdge, newConnection, els));
  }, []);

  const onEdgeUpdateEnd = useCallback((_, edge) => {
    console.log('onEdgeUpdateEnd')
    if (!edgeUpdateSuccessful.current) {
      setEdges((eds) => eds.filter((e) => e.id !== edge.id));
    }

    edgeUpdateSuccessful.current = true;
  }, []);

  const onNodeClick = useCallback((event, node) => {
    console.log('onNodeClick')
    console.dir(node);
    handleDialogClickOpen();
    setSelectedStep(workflowDefinitions.getStepById(node.id));
  }, [workflowDefinitions]);

  const onAddStep = useCallback(() => {
    console.log('onAddStep')
    const ui_config = new UIConfig();
    ui_config.pos_x = 100;
    ui_config.pos_y = 100;
    const step = new WorkflowStepDefinition();
    step.id = "step_" + Math.floor(Math.random() * 1000000);
    step.label = "New step";
    step.ui_config = ui_config;
    workflowDefinitions.steps.push(step);
    renderView(viewType);

  }, [workflowDefinitions, viewType]);

  const handleDialogClickOpen = () => {
    setDialogOpen(true);
  };

  const handleDialogClose = () => {
    setDialogOpen(false);
    renderView(viewType);
  };

  const handleStepConfigChange = (name: string, value: any) => {
    console.log('handleStepConfigChange')
    console.dir(selectedStep);

    if (selectedStep) {
      if (!selectedStep.params) {
        selectedStep.params = {}
      }
      if (name=="stype" ) {
        switch (value) {
        case "time_trigger":
          selectedStep.params = {"interval":"every 60 minutes"}
          break;
        case "start_workflow_task_step":
          selectedStep.params = {"workflow_name":"","sync":"false"}
          break;
        }
        selectedStep["stype"] = value;
      } else  {
        switch(name) {
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
      renderView(viewType);
    }
  }

  const onDownloadSuccess = (fileName:string , hash: string) => {
    console.log("onDownloadSuccess",fileName,hash)
    reloadWorkflows();
  }

  return (
    <div style={{ height: '85vh', width: '100vw' }}>
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
          <ToggleButton value="system">System</ToggleButton>
          <ToggleButton value="steps">Steps</ToggleButton>
          <ToggleButton value="combined">Combined</ToggleButton>
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
                <MenuItem  value="pystep">Python function</MenuItem>
                <MenuItem  value="http_trigger">HTTP trigger</MenuItem>
                <MenuItem  value="time_trigger">Time trigger</MenuItem>
                <MenuItem  value="start_workflow_task_step">Start workflow</MenuItem>
              </Select>

              <TextField sx={{ marginTop: 1 }} id="step-config-descr" fullWidth label="Description" size='small' variant="outlined" value={selectedStep?.description} onChange={(event) => { handleStepConfigChange("description", event.target.value) }} />
              {(selectedStep?.stype=="time_trigger") && (
              <TextField sx={{ marginTop: 1 }} id="step-config-time-config" fullWidth label="Time interval" size='small' variant="outlined" value={selectedStep?.params["interval"]} onChange={(event) => { handleStepConfigChange("time-interval", event.target.value) }} />
              )}
               {(selectedStep?.stype=="start_workflow_task_step") && (
              <TextField sx={{ marginTop: 1 }} id="step-start_workflow_task_step" fullWidth label="Name of the workflow" size='small' variant="outlined" value={selectedStep?.params["workflow_name"]} onChange={(event) => { handleStepConfigChange("workflow_name", event.target.value) }} />
              )}
               {(selectedStep?.stype=="start_workflow_task_step") && (
              <FormControlLabel control={<Checkbox checked={selectedStep?.params["sync"]=="true"} onChange={(event) => { handleStepConfigChange("workflow_sync_run_flag", event.target.checked) }} />} label="Synchronous execution" />
              )}
              <FormControlLabel control={<Checkbox checked={selectedStep?.enabled} onChange={(event) => { handleStepConfigChange("enabled", event.target.checked) }} />} label="Is enabled" />
              <FormControlLabel control={<Checkbox checked={selectedStep?.trigger} onChange={(event) => { handleStepConfigChange("trigger", event.target.checked) }} />} label="Is trigger" />
            </FormControl>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleDialogClose}>Cancel</Button>
            <Button onClick={handleDialogClose}>Save</Button>
          </DialogActions>
        </Dialog>
      </Box>
      <Stack direction="row" spacing={1} justifyContent="left"
        alignItems="left">
        <Item>
          <div style={{ height: '75vh', width: '70vw' }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodeClick={onNodeClick}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
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
            <Button variant="contained" onClick={reloadWorkflows} sx={{ marginTop: 2 , marginRight: 1 }} >Reload local workflows</Button>
            <Box sx={{ marginTop: 1 , marginBottom:1 }}>
              <CdfPublisher type="workflow"/>
              <CdfDownloader type="workflow-package" onDownloadSuccess={onDownloadSuccess} />
            </Box>

          </div>
        </Item>
        <Item >
        <WorkflowExecutionReport report={workflowStats} />
        </Item>
      </Stack>
    </div>


  );
}
