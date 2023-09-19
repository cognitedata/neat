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


export default function WorkflowDeleteDialog(props: any)
{
    const [dialogOpen, setDialogOpen] = useState(false);
    const [component, setComponent] = useState<WorkflowDefinition>(null);
    const handleDialogCancel = () => {
        setDialogOpen(false);
        props.onClose(component,"cancel");
    };
    const handleDelete = () => {

        
        setDialogOpen(false);
        props.onClose(component,"delete");
    };
   
    useEffect(() => {
        if (props.open){
            setDialogOpen(true);
            setComponent(props.component);
            console.dir(props.component);
        }
      }, [props.open]);



return (
<React.Fragment >
<IconButton color="warning" aria-label="add new workflow" onClick={(event)=>{setDialogOpen(true)} }>
    <RemoveCircleOutlineOutlinedIcon  />
</IconButton>
<Dialog open={dialogOpen} onClose={handleDialogCancel}>
<DialogTitle>Delete confirmation</DialogTitle>
<DialogContent>
    <p>Are you sure you want to delete workflow {props?.name}?</p>
</DialogContent>
<DialogActions>
  <Button variant="outlined" size="small" onClick={handleDelete}>Delete</Button>
  <Button variant="outlined" size="small" onClick={handleDialogCancel}>Cancel</Button>
</DialogActions>
</Dialog>
</React.Fragment>
)
}
