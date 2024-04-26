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
import { InputLabel, MenuItem, Select, ToggleButton, ToggleButtonGroup, Typography } from "@mui/material"
import { getNeatApiRootUrl } from "components/Utils"


export default function AddNewRulesaDialog(props: any) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [rules, setRules] = useState<any>({
        "role": "",
        "base_data_model": "",
        "name": "",
        "description": "",
        "rule_file": ""
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
        console.log(name, value);
        if (value == null) {
            return;
        }
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
                    <Typography variant="body1" color="textSecondary">Define your role:</Typography>
                    <ToggleButtonGroup
                        color="primary"
                        value={rules?.role}
                        exclusive
                        onChange={(event: React.SyntheticEvent, newValue: string) => { handleStepConfigChange("role", newValue) }}
                        aria-label="Platform"
                    >
                        <ToggleButton value="domain expert">
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                                <img width="70" src="./img/sme-icon.svg" alt="Domain expert" />
                                <span>Domain Expert</span>
                            </div>
                        </ToggleButton>
                        <ToggleButton value="information architect">
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                                <img width="70" src="./img/architect-icon.svg" alt="Information Architect" />
                                <span>Information Architect</span>
                            </div>
                        </ToggleButton>
                        <ToggleButton value="DMS Architect">
                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                                <img width="70" src="./img/developer-icon.svg" alt="DMS Expert" />
                                <span>CDF DM Expert</span>
                            </div>
                        </ToggleButton>
                    </ToggleButtonGroup>
                    <FormControl sx={{ width: 500, marginTop: 1 }} >
                        <InputLabel id="role-label">Base model</InputLabel>
                        <Select sx={{ marginTop: 1 }}
                            id="step-config-stype"
                            labelId="role-label"
                            value={rules?.base_data_model}
                            label="Your role"
                            size='small'
                            variant="outlined"
                            onChange={(event) => { handleStepConfigChange("base_data_model", event.target.value) }}
                        >
                            <MenuItem value="scratch">Start from scratch</MenuItem>
                            <MenuItem value="cdf_core">CDF Core model</MenuItem>
                            <MenuItem value="power_grid">Electrical grid model</MenuItem>
                        </Select>
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Data model name" size='small' variant="outlined" value={rules?.name} onChange={(event) => { handleStepConfigChange("name", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="Description" size='small' variant="outlined" value={rules?.description} onChange={(event) => { handleStepConfigChange("description", event.target.value) }} />
                        <TextField sx={{ marginTop: 1 }} fullWidth label="File name" size='small' variant="outlined" value={rules?.rule_file} onChange={(event) => { handleStepConfigChange("rule_file", event.target.value) }} />
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
