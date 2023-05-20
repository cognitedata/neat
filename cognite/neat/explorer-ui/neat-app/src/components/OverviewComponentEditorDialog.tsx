import Button from "@mui/material/Button"
import Dialog from "@mui/material/Dialog"
import DialogActions from "@mui/material/DialogActions"
import DialogContent from "@mui/material/DialogContent"
import DialogTitle from "@mui/material/DialogTitle"
import FormControl from "@mui/material/FormControl"
import TextField from "@mui/material/TextField"
import { useEffect, useState } from "react"
import { WorkflowStepsGroup } from "types/WorkflowTypes"

export default function OverviewComponentEditorDialog(props: any) 
{
    const [dialogOpen, setDialogOpen] = useState(false);
    const [component, setComponent] = useState<WorkflowStepsGroup>(null);
    const handleDialogClose = () => {
        setDialogOpen(false);
        props.onClose(component);
    };
    const handleStepConfigChange = (name: string, value: any) => {
        console.log('handleComponentConfigChange')
        let updComponent = Object.create(component);
        updComponent[name] = value;
        setComponent(updComponent);
        // component[name] = value;
    }
    useEffect(() => {
        if (props.open){
            setDialogOpen(true);
            setComponent(props.component);
            console.dir(props.component);
        }
      }, [props.open]);

    // useEffect(() => {
    //     if (dialogOpen){
    //         setComponent(props.component);
    //     }
    //     //     loadCdfResources(props.type);

    // }, [dialogOpen]);
return (
<Dialog open={dialogOpen} onClose={handleDialogClose}>
<DialogTitle>Component editor</DialogTitle>
<DialogContent>
  <FormControl sx={{ width: 300 }} >
    <TextField sx={{ marginTop: 1 }} id="step-config-id" fullWidth label="Component id" size='small' variant="outlined" value={component?.id} onChange={(event) => { handleStepConfigChange("id", event.target.value) }} />
    <TextField sx={{ marginTop: 1 }} id="step-config-label" fullWidth label="Label" size='small' variant="outlined" value={component?.label} onChange={(event) => { handleStepConfigChange("label", event.target.value) }} />
    <TextField sx={{ marginTop: 1 }} id="step-config-descr" fullWidth label="Description" size='small' variant="outlined" value={component?.description} onChange={(event) => { handleStepConfigChange("description", event.target.value) }} />
  </FormControl>
</DialogContent>
<DialogActions>
  <Button onClick={handleDialogClose}>Cancel</Button>
  <Button onClick={handleDialogClose}>Save</Button>
</DialogActions>
</Dialog>
)
}