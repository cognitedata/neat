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
import FileUpload from 'react-mui-fileuploader';
import { getNeatApiRootUrl, getSelectedWorkflowName } from './Utils';

export default function LocalUploader(props: any) {
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
        uploadFiles();
    };
    const handleStepConfigChange = (name: string, value: any) => {
        console.log('handleStepConfigChange')
        data[name] = value;
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
        let formData = new FormData()
        filesToUpload.forEach((file) => formData.append("files", file))

        fetch(neatApiRootUrl+"/api/file/upload/"+workflowName+"/rules", {
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
                title="Rules file uploader"
                multiFile={true}
                showPlaceholderImage={false}
                header="[Drag to drop new rules file here or click to select a file]"
                onFilesChange={handleFilesChange}
                onContextReady={(context) => {}}
                filesContainerHeight={100}
            />
                {error && <Container sx={{ color: 'red' }}>{error}</Container>}
            </DialogContent>
            <DialogActions>
                <Button onClick={handleDialogClose}>Cancel</Button>
                <Button onClick={handleDialogPublish}>Upload</Button>
            </DialogActions>
          </Dialog>
          <Button variant="outlined" sx={{ marginTop: 2, marginRight: 1 }} onClick={handleDialogClickOpen} >Upload to local storage </Button>
        </React.Fragment>
    )
}
