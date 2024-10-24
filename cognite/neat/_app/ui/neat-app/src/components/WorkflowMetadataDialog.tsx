import Button from "@mui/material/Button"
import Dialog from "@mui/material/Dialog"
import DialogActions from "@mui/material/DialogActions"
import DialogContent from "@mui/material/DialogContent"
import DialogTitle from "@mui/material/DialogTitle"
import FormControl from "@mui/material/FormControl"
import IconButton from "@mui/material/IconButton/IconButton"
import TextField from "@mui/material/TextField"
import React from "react"
import { useEffect, useState } from "react"
import { WorkflowDefinition } from "types/WorkflowTypes"
import AddCircleOutlineOutlinedIcon from '@mui/icons-material/AddCircleOutlineOutlined';


export default function WorkflowMetadataDialog(props: any)
{
    const [dialogOpen, setDialogOpen] = useState(false);
    const [component, setComponent] = useState<WorkflowDefinition>(null);
    const handleDialogSave = () => {
        setDialogOpen(false);
        props.onClose(component,"save");
    };
    const handleDialogCancel = () => {
        setDialogOpen(false);
        props.onClose(component,"cancel");
    };
    const handleDelete = () => {
        setDialogOpen(false);
        props.onClose(component,"delete");
    };
    const handleStepConfigChange = (name: string, value: any) => {
        let wdef = new WorkflowDefinition();
        if (component) {
            wdef.name = component.name;
            wdef.description = component.description;
        }

        switch (name) {
            case "name":
                wdef.name = value;
                break;
            case "description":
                wdef.description = value;
                break;
        }
        console.dir(wdef);
        setComponent(wdef);
    }
    useEffect(() => {
        if (props.open){
            setDialogOpen(true);
            setComponent(props.component);
            console.dir(props.component);
        }
      }, [props.open]);



return (
<React.Fragment >
<IconButton color="primary" aria-label="add new workflow" onClick={(event)=>{setDialogOpen(true)} }>
    <AddCircleOutlineOutlinedIcon />
</IconButton>
<Dialog open={dialogOpen} onClose={handleDialogCancel}>
<DialogTitle>Workflow editor</DialogTitle>
<DialogContent>
  <FormControl sx={{ width: 300 }} >
    <TextField sx={{ marginTop: 1 }} id="step-wf-name" fullWidth label="Unique name" size='small' variant="outlined" value={component?.name} onChange={(event) => { handleStepConfigChange("name", event.target.value) }} />
    <TextField sx={{ marginTop: 1 }} id="step-wf-description" fullWidth label="Description" size='small' variant="outlined" value={component?.description} onChange={(event) => { handleStepConfigChange("description", event.target.value) }} />
  </FormControl>
</DialogContent>
<DialogActions>
  <Button variant="outlined" size="small" onClick={handleDialogSave}>Save</Button>
  <Button variant="outlined" size="small" onClick={handleDialogCancel}>Cancel</Button>
</DialogActions>
</Dialog>
</React.Fragment>
)
}
