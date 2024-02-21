import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import React, { useEffect } from 'react';
import { useState } from 'react';
import { JsonViewer } from '@textea/json-viewer'

export default function NJsonViewer(props: any) {
    const [dialogOpen, setDialogOpen] = useState(false);
    const [data, setData] = useState<any>({});
    const [buttonLabel, setButtonLabel] = useState<any>(props.label ? props.label:"View full report");

    useEffect(() => {
        setData(props.data);
    }, [props.data]);

    const handleDialogClickOpen = () => {
        setDialogOpen(true);
        if (props.onOpen) {
            props.onOpen();
        }
    };

    const handleDialogClose = () => {
        setDialogOpen(false);
    };
    return (
        <React.Fragment>
          <Dialog open={dialogOpen} onClose={handleDialogClose} fullWidth={true} maxWidth="xl" >
            <DialogTitle>Data object viewer</DialogTitle>
            <DialogContent sx={{height:'90vh'}}>
                <JsonViewer value={data} />
            </DialogContent>
            <DialogActions>
                <Button onClick={handleDialogClose}>Close</Button>
            </DialogActions>
          </Dialog>
          <Button variant="outlined" size="small" sx={{ marginTop: 2, marginRight: 1 }} onClick={handleDialogClickOpen} > {buttonLabel} </Button>
        </React.Fragment>
    )
}
