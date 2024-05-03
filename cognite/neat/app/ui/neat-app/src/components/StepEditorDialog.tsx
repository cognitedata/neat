import Button from "@mui/material/Button"
import Checkbox from "@mui/material/Checkbox"
import { red } from "@mui/material/colors"
import Dialog from "@mui/material/Dialog"
import DialogActions from "@mui/material/DialogActions"
import DialogContent from "@mui/material/DialogContent"
import DialogTitle from "@mui/material/DialogTitle"
import FormControl from "@mui/material/FormControl"
import FormControlLabel from "@mui/material/FormControlLabel"
import MenuItem from "@mui/material/MenuItem"
import Select from "@mui/material/Select"
import TextField from "@mui/material/TextField"
import React, { ChangeEvent, useEffect, useState } from "react"
import { StepMetadata, StepRegistry, WorkflowDefinition, WorkflowStepDefinition, WorkflowSystemComponent } from "types/WorkflowTypes"
import { getNeatApiRootUrl } from "./Utils"
import LocalUploader from "./LocalUploader"
import WarningIcon from '@mui/icons-material/Warning';
import { Autocomplete, Box, Container, FormGroup, InputLabel, Link, List, ListItem, ListItemText, Stack, Tooltip, Typography, darken, lighten, styled } from "@mui/material"
import CheckCircleOutlineOutlinedIcon from '@mui/icons-material/CheckCircleOutlineOutlined';
import PlayCircleOutlineIcon from '@mui/icons-material/PlayCircleOutline';
import { Height } from "@mui/icons-material"

const GroupHeader = styled('div')(({ theme }) => ({
  position: 'sticky',
  top: '-8px',
  padding: '4px 10px',
  color: theme.palette.primary.main,
  backgroundColor:
    theme.palette.mode === 'light'
      ? lighten(theme.palette.primary.light, 0.85)
      : darken(theme.palette.primary.main, 0.8),
}));

const GroupItems = styled('ul')({
  padding: 0,
});

export default function StepEditorDialog(props: any)
{
    const [dialogOpen, setDialogOpen] = useState(false);
    const [selectedStep, setSelectedStep] = useState<WorkflowStepDefinition>();
    const neatApiRootUrl = getNeatApiRootUrl();
    const [runPayload,setRunPayload] = useState<string>(JSON.stringify({"action":"approve"}))
    const [statusText,setStatusText] = useState<string>("")
    const [stepRegistry,setStepRegistry] = useState<StepRegistry>()
    const [selectedStepTemplate,setSelectedStepTemplate] = useState<StepMetadata>()
    const [workflowDefinitions, setWorkflowDefinitions] = useState<WorkflowDefinition>();
    const [showStepIdError, setShowStepIdError] = useState(false);
    const [isConfigurationValid, setIsConfigurationValid] = useState(true);

    const handleDialogSave = () => {
        setDialogOpen(false);

        console.dir(selectedStep);
        props.onClose(selectedStep,"save");
        setShowStepIdError(false);
        setIsConfigurationValid(true);
    };
    const handleDialogCancel = () => {
        setDialogOpen(false);
        props.onClose(selectedStep,"cancel");
        setShowStepIdError(false);
        setIsConfigurationValid(true);
    };
    const handleDelete = () => {
        setDialogOpen(false);
        props.onClose(selectedStep,"delete");
        setShowStepIdError(false);
        setIsConfigurationValid(true);
    };

    const handleRunCommand = () => {
        setDialogOpen(false);
        // send POST request to run the step
        fetch(neatApiRootUrl +'/api/workflow/'+props.workflowName+'/http_trigger/'+selectedStep.id, { method: 'POST', body: runPayload })
        .then(response => response.json())
        .then(data => {

        }).catch((error) => {
            console.error('Error:', error);
        })
        props.onClose(selectedStep,"run");
    };

    const handleResumeCommand = () => {
      setDialogOpen(false);
      // send POST request to run the step
      fetch(neatApiRootUrl +'/api/workflow/'+props.workflowName+'/resume/'+selectedStep.id+'/default', { method: 'POST', body: runPayload })
      .then(response => response.json())
      .then(data => {

      }).catch((error) => {
          console.error('Error:', error);
      })
      props.onClose(selectedStep,"run");
  };

    const onUpload = (fileName:string , hash: string) => {

      setStatusText("File uploaded "+fileName)
    }

    useEffect(() => {
        if (props.open){
            setDialogOpen(true);
            if (props.step.stype == "stdstep") {
              setSelectedStepTemplate(props.stepRegistry?.getStepByName(props.step.method))
              let updStep = updateStepConfigsFromConfigurables(props.stepRegistry?.getStepByName(props.step.method),props.step,false)
              setSelectedStep(updStep);
            }else {
              setSelectedStep(props.step);
            }
            setStepRegistry(props.stepRegistry);
            setWorkflowDefinitions(props.workflowDefinitions);

            console.dir(props.stepRegistry);
        }
      }, [props.open]);

      // useEffect(() => {
      //   updateStepConfigsFromConfigurables(selectedStepTemplate,selectedStep,true);
      // }, [selectedStepTemplate]);


      const handleStepConfigurableChange = (name: string, value: any) => {

        console.dir(selectedStep);
        let updStep= Object.assign({},selectedStep);
        if (selectedStep) {
          if (!selectedStep.configs)
            selectedStep.configs = new Map<string,string>();
          selectedStep.configs[name] = value;
        }
        setSelectedStep(updStep);
      }

      const updateStepConfigsFromConfigurables = (stepTemplate: StepMetadata, currentStep:WorkflowStepDefinition,loadDefaults:boolean) =>  {
        // Configuring default valus from step template

        let updStep= Object.assign({},currentStep);
        if (!updStep.configs || loadDefaults) {
          updStep.configs = new Map<string,string>();
          updStep.complex_configs = new Map<string,Map<string,any>>();
        }
        if(!currentStep?.configs)
          currentStep.configs = new Map<string,string>();
        if(!currentStep?.complex_configs)
          currentStep.complex_configs = new Map<string,Map<string,any>>();
        for (let i=0;i<stepTemplate?.configurables.length;i++) {
          let confFromTemplate = stepTemplate?.configurables[i];
          if (confFromTemplate.type == "multi_select") {
            if (currentStep?.complex_configs[confFromTemplate.name] != undefined) {
              updStep.complex_configs[confFromTemplate.name] = currentStep?.complex_configs[confFromTemplate.name];
            } else {
              updStep.complex_configs[confFromTemplate.name] = new Map<string,boolean>();
              for (let j=0;j<confFromTemplate?.options.length;j++) {
                updStep.complex_configs[confFromTemplate.name][confFromTemplate?.options[j]] = false;
              }
            }
          }
          else{
            if (currentStep?.configs[confFromTemplate.name])
              updStep.configs[confFromTemplate.name] = currentStep?.configs[confFromTemplate.name];
            else
              updStep.configs[confFromTemplate.name] = confFromTemplate?.value;
          }

        }
        return updStep;
      }

      const handleStepConfigChange = (name: string, value: any) => {

        let updStep= Object.assign({},selectedStep);

        if (selectedStep) {
          if (!selectedStep.params) {
            selectedStep.params = {}
          }
          if (name == "stype") {
            switch (value) {
              case "time_trigger":
                updStep.params = { "interval": "every 60 minutes" }
                updStep.trigger = true;
                break;
              case "http_trigger":
                updStep.trigger = true;
                break;
              case "file_uploader":
                updStep.trigger = true;
                if( updStep.params["file_type"] == undefined)
                  updStep.params["file_type"] = "rules"
                break;

              case "start_workflow_task_step":
                updStep.params = { "workflow_name": "", "sync": "false" }
                break;
              case "stdstep":
                setSelectedStepTemplate(null)

            }
            updStep["stype"] = value;
          } else {
            switch (name) {
              case "id":
                // validate if id is unique
                let isUnique = workflowDefinitions?.isNewIdUnique(value);
                if (!isUnique) {
                  setShowStepIdError(true);
                  setIsConfigurationValid(false);
                } else {
                  setShowStepIdError(false);
                  setIsConfigurationValid(true);
                }
                updStep.id = value;
                break;
              case "method":
                if (selectedStep.stype == "stdstep") {
                  updStep = updateStepConfigsFromConfigurables(stepRegistry.getStepByName(value),updStep,true)
                  selectedStep.configs = updStep.configs;
                  setSelectedStepTemplate(stepRegistry.getStepByName(value))
                }
                updStep.method = value;
                break
              case "time-interval":
                updStep.params["interval"] = value;
                break;
              case "workflow_name":
                updStep.params["workflow_name"] = value;
                break;
              case "workflow_sync_run_flag":
                value = "false"
                if (value) {
                  value = "true"
                }
                updStep.params["sync"] = value;
                break;
              case "workflow_start_method":
                updStep.params["workflow_start_method"] = value;
                break;
              case "max_wait_time":
                updStep.params["max_wait_time"] = value;
                break;
              case "wait_timeout":
                updStep.params["wait_timeout"] = value;
                break;
              case "file_upload_type":
                updStep.params["file_type"] = value;
                break;
              default:
                updStep[name] = value;
            }
          }

        }
        setSelectedStep(updStep);
      }


  function checkboxHandler(configItemName:string,selectedItemName:string,checked:boolean): void {


    if (selectedStep) {
      let updStep= Object.assign({},selectedStep);
      if (!selectedStep.complex_configs)
        updStep.complex_configs = new Map<string,Map<string,boolean>>();

      if (selectedStep.complex_configs[configItemName]==undefined)
        updStep.complex_configs[configItemName] = new Map<string,boolean>( );

      updStep.complex_configs[configItemName][selectedItemName] = checked;
      console.dir(updStep)
      setSelectedStep(updStep);
    }

  }

return (
  <Dialog open={dialogOpen} onClose={handleDialogCancel} fullWidth={true}  maxWidth={"xl"} >
        <DialogTitle>Step configurator</DialogTitle>
        <DialogContent sx={{height:"90vh" }}>
          <FormControl  fullWidth>
            <TextField sx={{ marginTop: 1 }} id="step-config-id" fullWidth label="Step id" size='small' variant="outlined" value={selectedStep?.id} onChange={(event) => { handleStepConfigChange("id", event.target.value) }} />
            {showStepIdError && ( <Typography sx={{ marginTop: 1 }} color="error"> Step id must be unique </Typography>)}
            <TextField sx={{ marginTop: 1 }} id="step-config-label" fullWidth label="Label" size='small' variant="outlined" value={selectedStep?.label} onChange={(event) => { handleStepConfigChange("label", event.target.value) }} />
          </FormControl>
          <FormControl sx={{ marginTop: 2 }} fullWidth >
            <InputLabel id="step_type_label">Step type</InputLabel>
            <Select sx={{ marginTop: 1 }}
              id="step-config-stype"
              labelId="step_type_label"
              value={selectedStep?.stype}
              label="Step type"
              size='small'
              variant="outlined"
              onChange={(event) => { handleStepConfigChange("stype", event.target.value) }}
            >
              <MenuItem value="stdstep">Step library</MenuItem>
              <MenuItem value="file_uploader">File uploader</MenuItem>
              <MenuItem value="http_trigger">Workflow trigger</MenuItem>
              <MenuItem value="start_workflow_task_step">Multi-workflow trigger</MenuItem>
              <MenuItem value="time_trigger">Time trigger</MenuItem>
              <MenuItem value="wait_for_event">Wait for event</MenuItem>
            </Select>
          </FormControl>
          <FormControl sx={{ marginTop: 1 }} fullWidth >
            {(selectedStep?.stype == "time_trigger") && (
              <TextField sx={{ marginTop: 1 }} id="step-config-time-config" fullWidth label="Time interval" size='small' variant="outlined" value={selectedStep?.params["interval"]} onChange={(event) => { handleStepConfigChange("time-interval", event.target.value) }} />
            )}
            {(selectedStep?.stype == "stdstep") && (
              <Box>
              <FormControl sx={{ marginTop: 2 }} fullWidth >
              <Autocomplete
                disablePortal
                id="std-step-selector"
                options={stepRegistry.steps.sort((a, b) => -b.category.localeCompare(a.category))}
                value={selectedStepTemplate}
                isOptionEqualToValue={(option, value) => option.name === value.name }
                getOptionLabel={(option) => option.name}
                sx={{ marginBottom: 2 }}
                size='small'
                groupBy={(option) => option.category}
                renderGroup={(params) => (
                  <li key={params.key}>
                    <GroupHeader>{params.group}</GroupHeader>
                    <GroupItems>{params.children}</GroupItems>
                  </li>
                )}
                onChange={(event: React.SyntheticEvent, value, reason, details) => { handleStepConfigChange("method", value.name) }}
                renderInput={(params) => <TextField {...params} label="Step name" />}
              />
              </FormControl>
              {selectedStepTemplate && (
              <Box>
              <Stack direction="row" spacing={2}>
                <Typography sx={{marginRight:7}}>
                Version : <span style={{ color: selectedStepTemplate?.version.toLowerCase().includes("legacy") ? "red" : "green", fontWeight: selectedStepTemplate?.version.toLowerCase().includes("private-beta") ? "bold" : "bold" }}>{selectedStepTemplate?.version}</span>
                {selectedStepTemplate?.version.toLowerCase().includes("legacy") && (
                          <Tooltip title="Caution: This step is legacy step, meaning it can be only used with other legacy steps. We are not supporting it anymore.">
                            <WarningIcon sx={{ marginLeft: 1, marginBottom: -0.5, color: "orange" }} />
                          </Tooltip>
                )}
                 </Typography>
                <Link href={selectedStepTemplate?.docs_url} target="_blank"> Extended documentation </Link>
              </Stack>
              <Typography> Description : {selectedStepTemplate?.description} </Typography>
              <Typography> Input : <ul> {selectedStepTemplate?.input.map((item,i)=> (<li>  {workflowDefinitions?.isStepInputConfigured(selectedStep?.id,item, stepRegistry) && (<CheckCircleOutlineOutlinedIcon sx={{ marginBottom: -0.5 }} color="success"/>) }  {item}</li>)) } </ul> </Typography>
              <Typography> Output : <ul> {selectedStepTemplate?.output.map((item,i)=> (<li> {item} </li>))} </ul> </Typography>
              <Typography> Configurations : </Typography>
              <List sx={{ width: '100%', bgcolor: 'background.paper' }}>
              {selectedStepTemplate?.configurables.map((item,i)=> (
                <ListItem  sx={{
                  backgroundColor: item.label.toLowerCase().includes("warning") ? "yellow" : "inherit"
                }}>
                  <Box sx={{width:'50vw'}}>

                  <ListItemText
                    primary={item.name}
                    secondary={
                      <Box sx={{ display: "flex", alignItems: "center" }}>
                        {item.label.toLowerCase().includes("warning") && (
                          <WarningIcon sx={{ marginRight: 1, color: "orange" }} />
                        )}
                        {item.label}
                      </Box>
                    }
                  />
                  </Box>
                  <Box sx={{width:'50vw'}}>
                  <FormControl fullWidth>
                    {item?.options && selectedStep?.configs[item.name] != undefined  && item?.type != "multi_select"  && (
                    <Select
                      value={ selectedStep?.configs[item.name]}
                      size='small'
                      variant="outlined"
                      onChange={(event) => { handleStepConfigurableChange(item.name, event.target.value) }}
                      sx={{ marginBottom: 0 }}
                    >
                      {
                        item?.options && item.options.map((option, i) => (
                          <MenuItem value={option} key={option}> {option} </MenuItem>
                        ))
                      }
                    </Select> )}
                    { item?.type == "multi_select" && (
                        <FormGroup
                          sx={{ marginBottom: 0 }}
                        >
                          {
                            item?.options && item.options.map((option, i) => (
                              <FormControlLabel
                                control={<Checkbox checked = {selectedStep?.complex_configs[item.name][option]} onChange={ (event: ChangeEvent<HTMLInputElement>, checkedv: boolean)=>{ checkboxHandler(item.name,option,checkedv) } } name={option} />}
                                label={option}
                              />
                            ))
                          }
                        </FormGroup>
                    )}
                    {!item?.options && selectedStep?.configs && selectedStep?.configs[item.name] != undefined && item?.type != "password" && (
                      <TextField sx={{ marginTop: 0 }} fullWidth size='small' variant="outlined" value={ selectedStep?.configs[item.name]} onChange={(event) => { handleStepConfigurableChange(item.name, event.target.value) }} />
                    )}
                     {!item?.options && selectedStep?.configs && selectedStep?.configs[item.name] != undefined && item?.type == "password" && (
                      <TextField sx={{ marginTop: 0 }} fullWidth size='small' type="password" variant="outlined" value={ selectedStep?.configs[item.name]} onChange={(event) => { handleStepConfigurableChange(item.name, event.target.value) }} />
                    )}
                  </FormControl>
                  </Box>
                </ListItem>
              ))}
              </List>
              </Box>
              )}
              </Box>
            )}
            <TextField sx={{ marginTop: 1 }} id="step-config-descr" fullWidth label="Notes" size='small' variant="outlined" value={selectedStep?.description} onChange={(event) => { handleStepConfigChange("description", event.target.value) }} />

             {(selectedStep?.stype == "pystep") && (
              <TextField sx={{ marginTop: 1 }} id="step-pystep-method" fullWidth label="Override function name (optional)" size='small' variant="outlined" value={selectedStep?.method} onChange={(event) => { handleStepConfigChange("method", event.target.value) }} />
            )}
            {(selectedStep?.stype == "start_workflow_task_step") && (
              <TextField sx={{ marginTop: 1 }} id="step-start_workflow_task_step" fullWidth label="Name of the workflow" size='small' variant="outlined" value={selectedStep?.params["workflow_name"]} onChange={(event) => { handleStepConfigChange("workflow_name", event.target.value) }} />
            )}
            {(selectedStep?.stype == "start_workflow_task_step" || selectedStep?.stype == "http_trigger") && (
              <FormControlLabel control={<Checkbox checked={selectedStep?.params["sync"] == "true"} onChange={(event) => { handleStepConfigChange("workflow_sync_run_flag", event.target.checked) }} />} label="Synchronous execution" />
            )}
             <FormControlLabel control={<Checkbox checked={selectedStep?.enabled} onChange={(event) => { handleStepConfigChange("enabled", event.target.checked) }} />} label="Is step enabled" />
            {(selectedStep?.stype == "file_uploader") && (
              <Box>
                <FormControl fullWidth sx={{ marginTop: 2 }}>
                          <InputLabel id="file_uploader_file_type_label">Select File Type</InputLabel>
                          <Select sx={{ marginTop: 1 }}
                          labelId="file_uploader_file_type_label"
                          id="file_uploader_file_type"
                          value={selectedStep?.params["file_type"]}
                            label="Select File Type"
                          size='small'
                          variant="outlined"
                          onChange={(event) => { handleStepConfigChange("file_upload_type", event.target.value) }}
                        >
                          <MenuItem value="rules">Rules (Data Model) File</MenuItem>
                          <MenuItem value="staging">Staging File: Data dump in json/xml/csv format or any other file</MenuItem>
                          <MenuItem value="source_graph"> Source graph file in RDF format</MenuItem>
                        </Select>
                </FormControl>
                <LocalUploader
                  fileType={selectedStep?.params["file_type"]}
                  action="start_workflow"
                  onUpload={onUpload}
                  stepId={selectedStep.id}
                  workflowName={props.workflowName}
                />
              </Box>
            )}


            {(selectedStep?.trigger == false) && (
            <TextField sx={{ marginTop: 1 }} id="step-config-max-retries" fullWidth label="Max retries on failure" size='small' type="number" variant="outlined" value={selectedStep?.max_retries} onChange={(event) => { handleStepConfigChange("max_retries", event.target.value) }} />
            )}
             {(selectedStep?.trigger == false) && (
            <TextField sx={{ marginTop: 1 }} id="step-config-retry-delay" fullWidth label="Retry delay" size='small' variant="outlined" type="number" value={selectedStep?.retry_delay} onChange={(event) => { handleStepConfigChange("retry_delay", event.target.value) }} />
             )}
            </FormControl>
            {(selectedStep?.stype == "http_trigger") && (

                      <FormControl fullWidth sx={{ marginTop: 2 }}>
                          <InputLabel id="workflow_start_method_label">Workflow instance start method</InputLabel>
                          <Select sx={{ marginTop: 1 }}
                          labelId="workflow_start_method_label"
                          id="workflow_start_method"
                          value={selectedStep?.params["workflow_start_method"]}
                          label="Workflow instance start method"
                          size='small'
                          variant="outlined"
                          onChange={(event) => { handleStepConfigChange("workflow_start_method", event.target.value) }}
                        >
                          <MenuItem value="persistent_blocking">Start single global workflow instance in blocking mode (default)</MenuItem>
                          <MenuItem value="persistent_non_blocking">Start single global workflow instance in non-blocking mode</MenuItem>
                          <MenuItem value="ephemeral_instance">Start ephemeral workflow instance per request</MenuItem>
                        </Select>
                       </FormControl>
            )}
            <FormControl fullWidth sx={{ marginTop: 2 }}>
            {(selectedStep?.stype == "http_trigger" || selectedStep?.stype == "wait_for_event") && (
              <TextField sx={{ marginTop: 1 }} value={runPayload} label="Run payload"  size='small' variant="outlined"  onChange={(event)=>setRunPayload(event.target.value)} id="run_payload"> </TextField>
            )}
             {(selectedStep?.stype == "wait_for_event") && (
              <TextField sx={{ marginTop: 1 }} value={selectedStep?.params["wait_timeout"]} label="Time (in seconds) the system will wait before it times out and proceeds to next step.Default is 1 month"  size='small' variant="outlined"  onChange={(event) => { handleStepConfigChange("wait_timeout", event.target.value) }}  id="wait_timeout"> </TextField>
            )}
            {(selectedStep?.stype == "http_trigger" && selectedStep?.params["workflow_start_method"]=="persistent_blocking") && (
              <TextField sx={{ marginTop: 1 }} value={selectedStep?.params["max_wait_time"]}  size='small' variant="outlined"  label="Max blocking wait time" onChange={(event) => { handleStepConfigChange("max_wait_time", event.target.value) }} id="max_wait_time"> </TextField>
            )}
            </FormControl>

            {(selectedStep?.stype == "http_trigger") && (
              <Button sx={{ marginTop: 5 , width: "100%" , alignItems: 'center',justifyContent: 'center' }}  variant="outlined" size="small" color="success" onClick={handleRunCommand}> <PlayCircleOutlineIcon sx={{marginRight:2}}/> Start workflow </Button>
            )}
            {(selectedStep?.stype == "wait_for_event") && (
                <Button sx={{ marginTop: 5,  width: "100%" , alignItems: 'center',justifyContent: 'center' }}  variant="outlined" size="small" color="success" onClick={handleResumeCommand}> <PlayCircleOutlineIcon sx={{marginRight:2}}/> Resume workflow execution </Button>
            )}

          <Typography> {statusText} </Typography>


        </DialogContent>
        <DialogActions>
          <Button variant="outlined" size="small" disabled={!isConfigurationValid} onClick={handleDialogSave}>Save</Button>
          <Button variant="outlined" size="small" onClick={handleDialogCancel}>Cancel</Button>
          <Button variant="outlined" size="small" color="error" onClick={handleDelete} >Delete</Button>
        </DialogActions>
      </Dialog>
)
}
