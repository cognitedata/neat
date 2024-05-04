import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControl from '@mui/material/FormControl';
import TextField from '@mui/material/TextField';
import { Container } from '@mui/system';
import React, { useEffect } from 'react';
import { useState } from 'react';
import FileUpload from 'react-mui-fileuploader';
import { getNeatApiRootUrl, getSelectedWorkflowName } from './Utils';
import FormControlLabel from '@mui/material/FormControlLabel';
import Checkbox from '@mui/material/Checkbox';
import FileUploadIcon from '@mui/icons-material/FileUpload';

export default function LocalUploader(props: any) {
    const [dialogOpen, setDialogOpen] = useState(false);
    const [data, setData] = useState<any>({comments:"",author:""});
    const [error, setError] = useState<string>("");
    const handleDialogClickOpen = () => {
        setDialogOpen(true);
    };
    const [label,setLabel] = useState<string>("Upload File to NEAT local storage")
    const [postUploadConfigUpdate, setPostUploadConfigUpdate] = useState<boolean>(true);
    const [postUploadWorkflowStart , setPostUploadWorkflowStart] = useState<boolean>(false);

    // props.action
    useEffect(() => {
        setPostUploadWorkflowStart(props.action == "start_workflow");
        if (props.label){
            setLabel(props.label);
        }
    }, []);

    const handleDialogClose = () => {
        setDialogOpen(false);
    };
    const handleDialogPublish = () => {
        uploadFiles();
    };
    const handlePostUploadActionConfig = (name: string, value: any) => {

        if (name == "auto_config_update"){
            setPostUploadConfigUpdate(value);
        }else if (name == "auto_workflow_start"){
            setPostUploadWorkflowStart(value);
        }
    }

    const [filesToUpload, setFilesToUpload] = useState([])

    const handleFilesChange = (files) => {
        // Update chosen files
        setFilesToUpload([ ...files ])
    };

    const uploadFiles = () => {
        // Create a form and post it to server
        const neatApiRootUrl = getNeatApiRootUrl();
        const workflowName = getSelectedWorkflowName();
        let action = props.action;
        if (!action) {
            if (postUploadWorkflowStart && !postUploadConfigUpdate){
                action = "start_workflow"
            }else if (postUploadConfigUpdate && !postUploadWorkflowStart){
                action = "update_config"
            }else{
                action = "update_config_and_start_workflow"
            }
        }
        let formData = new FormData()
        filesToUpload.forEach((file) => formData.append("files", file))

        fetch(neatApiRootUrl+"/api/file/upload/"+props.workflowName+"/"+props.fileType+"/"+props.stepId+"/"+action, {
        method: "POST",
        body: formData
        }).then((response) => {
            if (response.ok) {
                setDialogOpen(false);
                return response.json();
            }else{
                setError(response.statusText);
            }

        }).then((data) => {
        const fileName = data.file_name;
        const fileHash = data.hash;
        props.onUpload(fileName, fileHash);
        setDialogOpen(false);
        }).catch((error) => {
            setError(error);
        } )
    }

    return (
        <React.Fragment>
          <Dialog open={dialogOpen} onClose={handleDialogClose}>
            <DialogTitle>Upload {props.type} to local storage</DialogTitle>
            <DialogContent>
            <FileUpload
                title="File uploader"
                multiFile={true}
                showPlaceholderImage={false}
                header="[Drag to drop the file here or click to select a file]"
                onFilesChange={handleFilesChange}
                onContextReady={(context) => {}}
                filesContainerHeight={100}
            />
            <FormControlLabel control={<Checkbox checked={postUploadConfigUpdate} onChange={(event) => { handlePostUploadActionConfig("auto_config_update", event.target.checked) }} />} label="Automatically update the references to file names and versions in all steps." />
            <FormControlLabel control={<Checkbox checked={postUploadWorkflowStart} onChange={(event) => { handlePostUploadActionConfig("auto_workflow_start", event.target.checked) }} />} label="Start the workflow once the upload has finished." />
            {error && <Container sx={{ color: 'red' }}>{error}</Container>}

            </DialogContent>
            <DialogActions>
                <Button onClick={handleDialogClose}>Cancel</Button>
                <Button onClick={handleDialogPublish}>Upload</Button>
            </DialogActions>
          </Dialog>
          <Button variant="outlined" sx={{ marginTop: 2, marginRight: 1 , width: "100%" , alignItems: 'center',justifyContent: 'center'  }} onClick={handleDialogClickOpen} > {label} <FileUploadIcon sx={{marginLeft:1}} /> </Button>
        </React.Fragment>
    )
}
