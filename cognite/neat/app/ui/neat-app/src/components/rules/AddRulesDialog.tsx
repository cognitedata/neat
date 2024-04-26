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
import { InputLabel, MenuItem, Select } from "@mui/material"
import { getNeatApiRootUrl } from "components/Utils"


export default function AddNewRulesaDialog(props: any) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [rules, setRules] = useState<any>({
        "role": "information architect",
        "base_data_model": "",
        "name": "",
        "description": "",
        "rule_file": "data-model-1.xlsx"
    });
    const handleDialogCreate = () => {
        // send new rules to the server
        fetch(neatApiRootUrl + '/api/rules/new', { method: 'POST', body: JSON.stringify(rules), headers: { 'Content-Type': 'application/json' } })
            .then(response => response.json())
            .then(data => {
                console.log('Success:', data);
                props.onCreated(data);
            }).catch((error) => {
                console.error('Error:', error);
            })
        setDialogOpen(false);
    };
    const handleDialogCancel = () => {
        setDialogOpen(false);
    };

    const handleStepConfigChange = (name: string, value: any) => {
        setRules({ ...rules, [name]: value });
    }
    useEffect(() => {
        if (props.open) {
            setDialogOpen(true);
            setRules(props.component);
            console.dir(props.component);
        }
    }, [props.open]);

    return (
        <React.Fragment >
            <IconButton color="primary" aria-label="add new workflow" onClick={(event) => { setDialogOpen(true) }}>
                <AddCircleOutlineOutlinedIcon />
            </IconButton>
            <Dialog open={dialogOpen} onClose={handleDialogCancel}>
                <DialogTitle>Create New Data Model</DialogTitle>
                <DialogContent>
                    <FormControl sx={{ width: 500, marginTop: 3 }} >
                        <InputLabel id="role-label">Set your role</InputLabel>
                        <Select sx={{ marginTop: 1 }}
                            id="step-config-stype"
                            labelId="role-label"
                            value={rules?.role}
                            label="Your role"
                            size='small'
                            variant="outlined"
                            onChange={(event) => { handleStepConfigChange("role", event.target.value) }}
                        >
                            <MenuItem value="domain expert">SME or Domain expert</MenuItem>
                            <MenuItem value="information architect">Information architect</MenuItem>
                            <MenuItem value="DMS Architect">CDF MD architect or developer</MenuItem>
                        </Select>
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Data model name" size='small' variant="outlined" value={rules?.name} onChange={(event) => { handleStepConfigChange("name", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Description" size='small' variant="outlined" value={rules?.description} onChange={(event) => { handleStepConfigChange("description", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="File name" size='small' variant="outlined" value={rules?.file_name} onChange={(event) => { handleStepConfigChange("rule_file", event.target.value) }} />
                    </FormControl>
                </DialogContent>
                <DialogActions>
                    <Button variant="outlined" size="small" onClick={handleDialogCreate}>Create</Button>
                    <Button variant="outlined" size="small" onClick={handleDialogCancel}>Cancel</Button>
                </DialogActions>
            </Dialog>
        </React.Fragment>
    )
}
