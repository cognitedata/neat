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
import RemoveCircleOutlineOutlinedIcon from '@mui/icons-material/RemoveCircleOutlineOutlined';
import { getNeatApiRootUrl, getSelectedWorkflowName } from "./Utils"


export default function WorkflowDeleteDialog(props: any)
{
    const neatApiRootUrl = getNeatApiRootUrl();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [component, setComponent] = useState<WorkflowDefinition>(null);

    const handleDialogCancel = () => {
        setDialogOpen(false);
    };

    const deleteWorkflow = () => {
        const url = neatApiRootUrl + "/api/workflow/" + getSelectedWorkflowName();
        fetch(url, {
          method: "delete", headers: {
            'Content-Type': 'application/json;charset=utf-8'
          }
        }).then((response) => response.json()).then((data) => {

              props.onDelete();
              setDialogOpen(false);
              window.location.reload();

        }).catch((error) => {
          console.error('Error:', error);
        })
    }

return (
<React.Fragment >
<IconButton color="warning" aria-label="add new workflow" onClick={(event)=>{setDialogOpen(true)} }>
    <RemoveCircleOutlineOutlinedIcon  />
</IconButton>
<Dialog open={dialogOpen} onClose={handleDialogCancel}>
<DialogTitle>Delete confirmation</DialogTitle>
<DialogContent>
    <p>Are you sure you want to delete workflow {getSelectedWorkflowName()}?</p>
</DialogContent>
<DialogActions>
  <Button variant="outlined" size="small" onClick={deleteWorkflow}>Delete</Button>
  <Button variant="outlined" size="small" onClick={handleDialogCancel}>Cancel</Button>
</DialogActions>
</Dialog>
</React.Fragment>
)
}
