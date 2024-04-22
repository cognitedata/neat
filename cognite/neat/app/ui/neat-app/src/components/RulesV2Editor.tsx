import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import React, { useEffect } from 'react';
import { useState } from 'react';
import { JsonViewer } from '@textea/json-viewer'

export default function InformationArchitectDataModelEditor(props: any) {
    const [dialogOpen, setDialogOpen] = useState(false);
    const [data, setData] = useState<any>({});
    const [buttonLabel, setButtonLabel] = useState<any>(props.label ? props.label:"View full report");

    useEffect(() => {
        setData(props.data);
        setDialogOpen(props.open);
    }, [props.data,props.open]);

    const handleDialogClickOpen = () => {
        setDialogOpen(true);
        if (props.onOpen) {
            props.onOpen();
        }
    };

    const handleDialogClose = () => {
        setDialogOpen(false);
        if (props.onClose) {
            props.onClose();
        }
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
        </React.Fragment>
    )
}
