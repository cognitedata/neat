import Button from "@mui/material/Button"
import Dialog from "@mui/material/Dialog"
import DialogActions from "@mui/material/DialogActions"
import DialogContent from "@mui/material/DialogContent"
import DialogTitle from "@mui/material/DialogTitle"
import FormControl from "@mui/material/FormControl"
import TextField from "@mui/material/TextField"
import { useEffect, useState } from "react"
import { WorkflowSystemComponent } from "types/WorkflowTypes"

export default function OverviewComponentEditorDialog(props: any)
{
    const [dialogOpen, setDialogOpen] = useState(false);
    const [component, setComponent] = useState<WorkflowSystemComponent>(null);
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

        console.dir(component);
        let updComponent = Object.assign({},component);
        updComponent[name] = value;

        console.dir(updComponent);
        setComponent(updComponent);
    }
    useEffect(() => {
        if (props.open){
            setDialogOpen(true);
            setComponent(props.component);
            console.dir(props.component);
        }
      }, [props.open]);



return (
<Dialog open={dialogOpen} onClose={handleDialogCancel}>
<DialogTitle>Component editor</DialogTitle>
<DialogContent>
  <FormControl sx={{ width: 300 }} >
    <TextField sx={{ marginTop: 1 }} id="step-config-id" fullWidth label="Component id" size='small' variant="outlined" value={component?.id} onChange={(event) => { handleStepConfigChange("id", event.target.value) }} />
    <TextField sx={{ marginTop: 1 }} id="step-config-label" fullWidth label="Label" size='small' variant="outlined" value={component?.label} onChange={(event) => { handleStepConfigChange("label", event.target.value) }} />
    <TextField sx={{ marginTop: 1 }} id="step-config-descr" fullWidth label="Description" size='small' variant="outlined" value={component?.description} onChange={(event) => { handleStepConfigChange("description", event.target.value) }} />
  </FormControl>
</DialogContent>
<DialogActions>
  <Button variant="outlined" size="small" onClick={handleDialogSave}>Save</Button>
  <Button variant="outlined" size="small" onClick={handleDialogCancel}>Cancel</Button>
  <Button variant="outlined" size="small" color="error" onClick={handleDelete}>Delete</Button>
</DialogActions>
</Dialog>
)
}
