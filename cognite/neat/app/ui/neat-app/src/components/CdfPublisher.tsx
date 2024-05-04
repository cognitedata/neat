import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControl from '@mui/material/FormControl';
import TextField from '@mui/material/TextField';
import { Container } from '@mui/system';
import React from 'react';
import { useState } from 'react';
import { getNeatApiRootUrl, getSelectedWorkflowName } from './Utils';

export default function CdfPublisher(props: any) {
    const [dialogOpen, setDialogOpen] = useState(false);
    const [data, setData] = useState<any>({comments:"",author:""});
    const [error, setError] = useState<string>("");
    const handleDialogClickOpen = () => {
        setDialogOpen(true);
    };

    const handleDialogClose = () => {
        setDialogOpen(false);
    };
    const handleDialogPublish = () => {
        uploadWorkflowToCdf();
    };
    const handleStepConfigChange = (name: string, value: any) => {

        data[name] = value;
    }

    const uploadWorkflowToCdf = () => {
        // Create a form and post it to server
        const neatApiRootUrl = getNeatApiRootUrl();
        const workflowName = getSelectedWorkflowName();
        let request = {"comments":data.comments,"author":data.author,"tag":data.tag}
        let url = "";
        if (props.type =="transformation rules"){
            request["file_name"] = props.fileName;
            url = neatApiRootUrl+"/api/workflow/upload-rules-cdf/"+workflowName
        }else if (props.type =="workflow"){
            url = neatApiRootUrl+"/api/workflow/upload-wf-to-cdf/"+workflowName
        }

        fetch(url, {
          method: "POST",
          body: JSON.stringify(request),
          headers: {
            'Content-Type': 'application/json;charset=utf-8'
          }
        }).then((response) => {
            if (response.ok) {
                setDialogOpen(false);
            }else{
                setError(response.statusText);
            }

        }).catch((error) => {
            setError(error);
        } )
      }

    return (
        <React.Fragment>
          <Dialog open={dialogOpen} onClose={handleDialogClose}>
            <DialogTitle>Publish {props.type} to CDF</DialogTitle>
            <DialogContent>
                <FormControl sx={{ width: 400 }} >
                <TextField sx={{ marginTop: 1 }} id="step-config-comments" fullWidth label="Comments" size='small' variant="outlined"   onChange={(event) => { handleStepConfigChange("comments", event.target.value) }} />
                <TextField sx={{ marginTop: 1 }} id="step-config-author" fullWidth label="Author" size='small' variant="outlined"  onChange={(event) => { handleStepConfigChange("author", event.target.value) }} />
                <TextField sx={{ marginTop: 1 }} id="step-config-tag" fullWidth label="Tag" size='small' variant="outlined"  onChange={(event) => { handleStepConfigChange("tag", event.target.value) }} />
                </FormControl>
                {error && <Container sx={{ color: 'red' }}>{error}</Container>}
            </DialogContent>
            <DialogActions>
                <Button onClick={handleDialogClose}>Cancel</Button>
                <Button onClick={handleDialogPublish}>Publish</Button>
            </DialogActions>
          </Dialog>
          <Button variant="outlined" sx={{ marginTop: 2, marginRight: 1 }} onClick={handleDialogClickOpen} >Publish from NEAT to CDF </Button>
        </React.Fragment>
    )
}
