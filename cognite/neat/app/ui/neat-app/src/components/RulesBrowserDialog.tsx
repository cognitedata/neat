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
import { List, ListItem, ListItemButton, ListItemText } from "@mui/material"
import TravelExploreIcon from '@mui/icons-material/TravelExplore';


export default function RulesBrowserDialog(props: any)
{
    const neatApiRootUrl = getNeatApiRootUrl();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [rules, setRules] = useState<string[]>([]);

    const handleDialogCancel = () => {
        setDialogOpen(false);
    };



    const loadListOfRules = () => {
        const url = neatApiRootUrl + "/api/rules/list";
        fetch(url, {
          method: "get", headers: {
            'Content-Type': 'application/json;charset=utf-8'
          }
        }).then((response) => response.json()).then((data) => {
            console.log("Rules loaded");
            setRules(data.result);

        }).catch((error) => {
          console.error('Error:', error);
        })
    }

    useEffect(() => {
        setDialogOpen(false);
        loadListOfRules();
    }, []);

    const onSelectRule = (rule: string) => {
        props.onSelectRule(rule);
        setDialogOpen(false);
    }

return (
<React.Fragment >
<IconButton color="info" aria-label="open browser" onClick={(event)=>{setDialogOpen(true)} }>
    <TravelExploreIcon  />
</IconButton>
<Dialog open={dialogOpen}  onClose={handleDialogCancel} >
<DialogTitle>Data modele (rules) browser </DialogTitle>
<DialogContent sx={{height:"60vh"}} >
    {/* render list of rules */}
    <List>
        {rules.map((rule, index) => {
            return <ListItem key={index}>
                 <ListItemButton onClick={(event) => {onSelectRule(rule)}}>
                    <ListItemText primary={rule}  />
                </ListItemButton>
               </ListItem>
        })}
    </List>
</DialogContent>
<DialogActions>
  <Button variant="outlined" size="small" onClick={handleDialogCancel}>Close</Button>
</DialogActions>
</Dialog>
</React.Fragment>
)
}
