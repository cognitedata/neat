import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import FormControl from '@mui/material/FormControl';
import TextField from '@mui/material/TextField';
import { Container } from '@mui/system';
import { DataGrid } from '@mui/x-data-grid/DataGrid';
import { GridColDef } from '@mui/x-data-grid/models/colDef';
import React, { useEffect } from 'react';
import { useState } from 'react';
import { getNeatApiRootUrl, getSelectedWorkflowName } from './Utils';

export  class NeatCdfResource {
    id: number;
    name: string;
    rtype: string;
    last_updated_time: number | null = null;
    last_updated_time_str: string | null = null;
    last_updated_by: string | null = null;
    version: string | null = null;
    tag: string | null = null;
    comments: string | null = null;
    external_id: string | null = null;
    is_latest: boolean = false;
}

export default function CdfDownloader(props: any) {
    const [dialogOpen, setDialogOpen] = useState(false);
    const [data, setData] = useState<NeatCdfResource[]>([]);
    const [error, setError] = useState<string>("");
    const [selectedRow, setSelectedRow] = useState<NeatCdfResource | null>(null);

    const handleDialogClickOpen = () => {
        setDialogOpen(true);
    };

    useEffect(() => {
        if (dialogOpen)
            loadCdfResources(props.type);
    }, [dialogOpen]);

    const handleDialogClose = () => {
        setDialogOpen(false);
    };
    const handleDialogDownload = () => {
        console.dir(selectedRow);
        downloadFromCdfToLocalStore();
    };

    const loadCdfResources = (resourceType: string = "") => {
        const neatApiRootUrl = getNeatApiRootUrl();
        const url = neatApiRootUrl+"/api/cdf/neat-resources?"+new URLSearchParams({"resource_type":resourceType}).toString();
        fetch(url).then((response) => response.json()).then((data) => {
            console.log('Success:', data);
            // modify each row
            for (let i = 0; i < data.result.length; i++) {
                data.result[i].last_updated_time_str = new Date(data.result[i].last_updated_time).toLocaleString();
            }
            setData(data.result);
        }).catch((error) => {
          console.error('Error:', error);
        }).finally(() => { });
      }

    const downloadFromCdfToLocalStore = () => {
        // Create a form and post it to server
        const neatApiRootUrl = getNeatApiRootUrl();
        const workflowName = getSelectedWorkflowName();
        let request = {"file_name":selectedRow.name,"version":selectedRow.version}
        let url = "";
        if (props.type =="neat-wf-rules"){
            url = neatApiRootUrl+"/api/workflow/download-rules-from-cdf"
        }else if (props.type =="workflow-package"){
            url = neatApiRootUrl+"/api/workflow/download-wf-from-cdf"
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
                props?.onDownloadSuccess(selectedRow.name,selectedRow.version);
            }else{
                setError(response.statusText);
            }

        }).catch((error) => {
            setError(error);
        } )
      }

    const columns: GridColDef[] = [
        { field: 'name', headerName: 'Name', width: 300 },
        { field: 'last_updated_time_str', headerName: 'Updated at', width: 170 },
        { field: 'last_updated_by', headerName: 'Updated by', width: 150 },
        { field: 'version', headerName: 'Version', width: 290 },
        { field: 'tag', headerName: 'Tag', width: 150 },
        { field: 'comments', headerName: 'Comments', width: 400 },

    ];
    return (
        <React.Fragment>
          <Dialog open={dialogOpen} onClose={handleDialogClose} fullWidth={true} maxWidth="xl" >
            <DialogTitle>Download {props.type} from CDF</DialogTitle>
            <DialogContent sx={{height:500}}>
            <DataGrid
                rows={data}
                columns={columns}
                pageSize={100}
                onSelectionModelChange = {(newSelectionIds) => {
                    console.log(newSelectionIds);
                    if (newSelectionIds.length > 0){
                        // find the selected row by id
                        const selectedRow = data.find((row) => row.id == newSelectionIds[0]);
                        setSelectedRow(selectedRow);
                    }
                }}
                rowsPerPageOptions={[10]}
            />
                {error && <Container sx={{ color: 'red' }}>{error}</Container>}
            </DialogContent>
            <DialogActions>
                <Button onClick={handleDialogClose}>Cancel</Button>
                <Button onClick={handleDialogDownload}>Download</Button>
            </DialogActions>
          </Dialog>
          <Button variant="outlined" sx={{ marginTop: 2, marginRight: 1 }} onClick={handleDialogClickOpen} >Download from CDF to NEAT </Button>
        </React.Fragment>
    )
}
