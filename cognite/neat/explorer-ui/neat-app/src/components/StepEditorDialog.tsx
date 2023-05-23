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
import { useEffect, useState } from "react"
import { WorkflowStepDefinition, WorkflowSystemComponent } from "types/WorkflowTypes"
import { getNeatApiRootUrl } from "./Utils"

export default function StepEditorDialog(props: any)
{
    const [dialogOpen, setDialogOpen] = useState(false);
    const [selectedStep, setSelectedStep] = useState<WorkflowStepDefinition>();
    const neatApiRootUrl = getNeatApiRootUrl();
    const [runPayload,setRunPayload] = useState<string>(JSON.stringify({"action":"approve"}))

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

    useEffect(() => {
        if (props.open){
            setDialogOpen(true);
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
            {(selectedStep?.stype == "http_trigger" || selectedStep?.stype == "wait_for_event") && (
              <TextField sx={{ marginTop: 1 }} value={runPayload} onChange={(event)=>setRunPayload(event.target.value)} id="run_payload"> </TextField>
            )}
          </FormControl>

        </DialogContent>
        <DialogActions>
          <Button variant="outlined" size="small" onClick={handleDialogSave}>Save</Button>
          <Button variant="outlined" size="small" onClick={handleDialogCancel}>Cancel</Button>
          <Button variant="outlined" size="small" color="error" onClick={handleDelete} >Delete</Button>
          {(selectedStep?.stype == "http_trigger" || selectedStep?.stype == "wait_for_event") && (
              <Button variant="outlined" size="small" color="success" onClick={handleRunCommand}>Run</Button>
          )}

        </DialogActions>
      </Dialog>
)
}
