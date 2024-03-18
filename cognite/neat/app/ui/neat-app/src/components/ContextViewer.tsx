import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogActions from '@mui/material/DialogActions';
import DialogContent from '@mui/material/DialogContent';
import DialogTitle from '@mui/material/DialogTitle';
import React, { useEffect } from 'react';
import { useState } from 'react';
import { JsonViewer } from '@textea/json-viewer'
import { getNeatApiRootUrl, getSelectedWorkflowName } from './Utils';
import { Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Paper, Link } from '@mui/material';
import { Anchor } from '@mui/icons-material';
import NJsonViewer from './JsonViewer';


export default function ContextViewer(props: any) {
    const neatApiRootUrl = getNeatApiRootUrl();
    const [dialogOpen, setDialogOpen] = useState(false);
    const [context, setContext] = useState<any>([]);
    const [workflowName, setWorkflowName] = useState<string>("");
    const [contextItem, setContextItem] = useState<any>(null);


    const handleDialogClickOpen = () => {
        setWorkflowName(getSelectedWorkflowName());
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

    const openQuickView = (itemName:string) => {
        const url = neatApiRootUrl + "/api/workflow/context/" + getSelectedWorkflowName() + "/object_name/" + itemName;
        setContextItem({"Loading" : "Loading object"});
        fetch(url).then((response) => {
          if (!response.ok) {
            setContextItem({"Error" : "Error fetching or serializng object"});
            return {"Error1" : "Error fetching or serializng object"};
          }else {
            return response.json()
          }

        }).then((data) => {
          setContextItem(data);
        }
        ).catch((error) => {
          console.error('Error:', error);
          setContextItem({"Error" : "  Error fetching or serializng object"});
        })

    }

    return (

                    <React.Fragment>
                      <Dialog open={dialogOpen} onClose={handleDialogClose} fullWidth={true} maxWidth="xl">
                        <DialogTitle>Workflow context viewer</DialogTitle>
                        <DialogContent sx={{ height: '70vh' }}>
                          <TableContainer component={Paper}>
                            <Table>
                              <TableHead>
                                <TableRow>
                                  <TableCell>
                                    <strong>Context variable name</strong>
                                  </TableCell>
                                  <TableCell>
                                    <strong>Type</strong>
                                  </TableCell>
                                  <TableCell>
                                    <strong>Value</strong>
                                  </TableCell>
                                </TableRow>
                              </TableHead>
                              <TableBody>
                                {context.map((item) => (
                                  <TableRow key={item.name}>
                                    <TableCell>{item.name}</TableCell>
                                    <TableCell>{item.type}</TableCell>
                                    <TableCell> <NJsonViewer data={contextItem} label ="Quick viewer" onOpen = {()=>{ openQuickView(item.name) }} />
                                    <Button variant="outlined" size='small' sx={{ marginTop: 2, marginRight: 1 }}
                                      onClick={() => window.open("/api/workflow/context/"+workflowName+"/object_name/"+item.name, "_blank")}>Open Object in a new tab</Button>
                                    </TableCell>
                                  </TableRow>
                                ))}
                              </TableBody>
                            </Table>
                          </TableContainer>
                        </DialogContent>
                        <DialogActions>
                          <Button onClick={handleDialogClose}>Close</Button>
                        </DialogActions>
                      </Dialog>
                      <Button variant="outlined" sx={{ marginTop: 2, marginRight: 1 }} onClick={handleDialogClickOpen}>
                        Context viewer
                      </Button>
                    </React.Fragment>

    )
}
