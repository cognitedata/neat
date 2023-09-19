import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import React, { useEffect } from 'react';
import { useState } from 'react';
import { JsonViewer } from '@textea/json-viewer'
import { getNeatApiRootUrl, getSelectedWorkflowName } from './Utils';

export default function ContextViewer(props: any) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [context, setContext] = useState<any>({});
    const handleDialogClickOpen = () => {
        loadContext();
        setDialogOpen(true);
    };

    const loadContext = () => {
        const url = neatApiRootUrl + "/api/workflow/context/" + getSelectedWorkflowName();
        fetch(url).then((response) => response.json()).then((data) => {
          setContext(data.context);
        }
        ).catch((error) => {
          console.error('Error:', error);
        })
      };

    const handleDialogClose = () => {
        setDialogOpen(false);
    };
    return (
        <React.Fragment>
          <Dialog open={dialogOpen} onClose={handleDialogClose} fullWidth={true} maxWidth="xl" >
            <DialogTitle>Workflow context viewer</DialogTitle>
            <DialogContent sx={{height:'70vh'}}>
                <JsonViewer value={context} />
            </DialogContent>
            <DialogActions>
                <Button onClick={handleDialogClose}>Close</Button>
            </DialogActions>
          </Dialog>
          <Button variant="outlined" sx={{ marginTop: 2, marginRight: 1 }} onClick={handleDialogClickOpen} > Context viewer</Button>
        </React.Fragment>
    )
}
