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
import React, { useEffect, useState } from "react"
import { WorkflowStepDefinition, WorkflowSystemComponent } from "types/WorkflowTypes"
import { getNeatApiRootUrl } from "./Utils"
import LocalUploader from "./LocalUploader"
import { InputLabel, Typography } from "@mui/material"

export default function StepEditorDialog(props: any)
{
    const [dialogOpen, setDialogOpen] = useState(false);
    const [selectedStep, setSelectedStep] = useState<WorkflowStepDefinition>();
    const neatApiRootUrl = getNeatApiRootUrl();
    const [runPayload,setRunPayload] = useState<string>(JSON.stringify({"action":"approve"}))
    const [statusText,setStatusText] = useState<string>("")

    const handleDialogSave = () => {
        setDialogOpen(false);
        props.onClose(selectedStep,"save");
    };
    const handleDialogCancel = () => {
        setDialogOpen(false);
        props.onClose(selectedStep,"cancel");
    };
    const handleDelete = () => {
        setDialogOpen(false);
        props.onClose(selectedStep,"delete");
    };

    const handleRunCommand = () => {
        setDialogOpen(false);
        // send POST request to run the step
        fetch(neatApiRootUrl +'/api/workflow/'+props.workflowName+'/http_trigger/'+selectedStep.id, { method: 'POST', body: runPayload })
        .then(response => response.json())
        .then(data => {
            console.log('Success:', data);
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
          console.log('Success:', data);
      }).catch((error) => {
          console.error('Error:', error);
      })
      props.onClose(selectedStep,"run");
  };

    const onUpload = (fileName:string , hash: string) => {
      console.log("onUpload",fileName,hash)
      setStatusText("File uplloaded "+fileName)
    }

    useEffect(() => {
        if (props.open){
            setDialogOpen(true);
            if (!selectedStep?.params["workflow_start_method"])
              selectedStep.params["workflow_start_method"] = "persistent_blocking"
            setSelectedStep(props.step);
            console.dir(props.step);
        }
      }, [props.open]);

      const handleStepConfigChange = (name: string, value: any) => {
        console.log('handleStepConfigChange')
        console.dir(selectedStep);
        let updStep= Object.assign({},selectedStep);

        if (selectedStep) {
          if (!selectedStep.params) {
            selectedStep.params = {}
          }
          if (name == "stype") {
            switch (value) {
              case "time_trigger":
                updStep.params = { "interval": "every 60 minutes" }
                break;
              case "start_workflow_task_step":
                updStep.params = { "workflow_name": "", "sync": "false" }
                break;
            }
            updStep["stype"] = value;
          } else {
            switch (name) {
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
              default:
                updStep[name] = value;
            }
          }
          console.log("rendering view")
        }
        setSelectedStep(updStep);
      }


return (
  <Dialog open={dialogOpen} onClose={handleDialogCancel}>
        <DialogTitle>Step configurator</DialogTitle>
        <DialogContent >
          <FormControl  fullWidth>
            <TextField sx={{ marginTop: 1 }} id="step-config-id" fullWidth label="Step id" size='small' variant="outlined" value={selectedStep?.id} onChange={(event) => { handleStepConfigChange("id", event.target.value) }} />
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
              <MenuItem value="pystep">Python function</MenuItem>
              <MenuItem value="http_trigger">HTTP trigger</MenuItem>
              <MenuItem value="time_trigger">Time trigger</MenuItem>
              <MenuItem value="wait_for_event">Wait for event</MenuItem>
              <MenuItem value="start_workflow_task_step">Start workflow</MenuItem>
              <MenuItem value="file_uploader">File uploader</MenuItem>
            </Select>
          </FormControl>
          <FormControl sx={{ marginTop: 1 }} fullWidth >
            <TextField sx={{ marginTop: 1 }} id="step-config-descr" fullWidth label="Description" size='small' variant="outlined" value={selectedStep?.description} onChange={(event) => { handleStepConfigChange("description", event.target.value) }} />
            {(selectedStep?.stype == "time_trigger") && (
              <TextField sx={{ marginTop: 1 }} id="step-config-time-config" fullWidth label="Time interval" size='small' variant="outlined" value={selectedStep?.params["interval"]} onChange={(event) => { handleStepConfigChange("time-interval", event.target.value) }} />
            )}
             {(selectedStep?.stype == "pystep") && (
              <TextField sx={{ marginTop: 1 }} id="step-pystep-method" fullWidth label="Override function name (optional)" size='small' variant="outlined" value={selectedStep?.method} onChange={(event) => { handleStepConfigChange("method", event.target.value) }} />
            )}
            {(selectedStep?.stype == "start_workflow_task_step") && (
              <TextField sx={{ marginTop: 1 }} id="step-start_workflow_task_step" fullWidth label="Name of the workflow" size='small' variant="outlined" value={selectedStep?.params["workflow_name"]} onChange={(event) => { handleStepConfigChange("workflow_name", event.target.value) }} />
            )}
            {(selectedStep?.stype == "start_workflow_task_step" || selectedStep?.stype == "http_trigger") && (
              <FormControlLabel control={<Checkbox checked={selectedStep?.params["sync"] == "true"} onChange={(event) => { handleStepConfigChange("workflow_sync_run_flag", event.target.checked) }} />} label="Synchronous execution" />
            )}
            {(selectedStep?.stype == "file_uploader") && (
               <LocalUploader fileType="staging" action="start_workflow" onUpload={onUpload} stepId={selectedStep.id} workflowName={props.workflowName} />
            )}

            <FormControlLabel control={<Checkbox checked={selectedStep?.enabled} onChange={(event) => { handleStepConfigChange("enabled", event.target.checked) }} />} label="Is step enabled" />
            <FormControlLabel control={<Checkbox checked={selectedStep?.trigger} onChange={(event) => { handleStepConfigChange("trigger", event.target.checked) }} />} label="Is trigger step" />
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
            {(selectedStep?.stype == "http_trigger" && selectedStep?.params["workflow_start_method"]=="persistent_blocking") && (
              <TextField sx={{ marginTop: 1 }} value={selectedStep?.params["max_wait_time"]}  size='small' variant="outlined"  label="Max blocking wait time" onChange={(event) => { handleStepConfigChange("max_wait_time", event.target.value) }} id="max_wait_time"> </TextField>
            )}
            </FormControl>
         
          <Typography> {statusText} </Typography>

        </DialogContent>
        <DialogActions>
          <Button variant="outlined" size="small" onClick={handleDialogSave}>Save</Button>
          <Button variant="outlined" size="small" onClick={handleDialogCancel}>Cancel</Button>
          <Button variant="outlined" size="small" color="error" onClick={handleDelete} >Delete</Button>
          {(selectedStep?.stype == "http_trigger") && (
              <Button variant="outlined" size="small" color="success" onClick={handleRunCommand}>Run</Button>
          )}
          {(selectedStep?.stype == "wait_for_event") && (
              <Button variant="outlined" size="small" color="success" onClick={handleResumeCommand}>Resume execution</Button>
          )}

        </DialogActions>
      </Dialog>
)
}
