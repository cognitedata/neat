import Button from "@mui/material/Button"
import Dialog from "@mui/material/Dialog"
import DialogActions from "@mui/material/DialogActions"
import DialogContent from "@mui/material/DialogContent"
import DialogTitle from "@mui/material/DialogTitle"
import React, { useEffect, useState } from "react"
import RemoveNsPrefix, { getNeatApiRootUrl, getSelectedWorkflowName } from "./Utils"
import { Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material"
import { ExplorerContext } from "./Context"

export default function NodeViewerDialog(props: any)
{   
    const {hiddenNsPrefixModeCtx, graphNameCtx} = React.useContext(ExplorerContext);
    const [dialogOpen, setDialogOpen] = useState(false);
    const neatApiRootUrl = getNeatApiRootUrl();
    const [nodeId, setNodeId] = useState("");
    const [graphName, setGraphName] = graphNameCtx;
    const [hiddenNsPrefixMode, setHiddenNsPrefixMode] = hiddenNsPrefixModeCtx;
    const [data, setData] = useState([]);
   
    const handleDialogCancel = () => {
        setDialogOpen(false);
        props.onClose();
    };
    
    useEffect(() => {
        if (props.open){
            setNodeId(props.nodeId);
            setDialogOpen(true);
            loadObjectProperties(props.nodeId);
        }
      }, [props.open]);

      const loadObjectProperties = (reference:string) => {
        const workflowName = getSelectedWorkflowName();
        fetch(neatApiRootUrl+`/api/object-properties?`+new URLSearchParams({"reference":reference,"graph_name":graphName,"workflow_name":workflowName}).toString())
         .then((response) => response.json())
          .then((rdata) => {
            let result = rdata.rows.map((row:any) => {
                let prop = row.property;
                if(hiddenNsPrefixMode) 
                  prop = RemoveNsPrefix(prop);
                return {property:prop, value:row.value}
            });
            setData(result);
          }).catch((error) => {
            console.error('Error:', error);
          });
       }
      

return (
  <Dialog open={dialogOpen} onClose={handleDialogCancel} fullWidth = {true} maxWidth = "lg"  >
        <DialogTitle>Node viewer</DialogTitle>
        <DialogContent sx={{ minWidth: 650 }} >
        <TableContainer component={Paper}>
      <Table sx={{ minWidth: 650 }} aria-label="simple table">
        <TableHead>
          <TableRow>
            <TableCell>Property</TableCell>
            <TableCell align="left">Value</TableCell>
           </TableRow>
        </TableHead>
        <TableBody>
          {data.map((row) => (
            <TableRow
              key={row.name}
              sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
            >
              <TableCell component="th" scope="row">
                {row.property}
              </TableCell>
              <TableCell align="left">{ row.value } </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer> 
            <Typography variant="body1" gutterBottom> object : { nodeId} </Typography>
        </DialogContent>
        <DialogActions>
          <Button variant="outlined" size="small" onClick={handleDialogCancel}>Cancel</Button>
        </DialogActions>
      </Dialog>
)
}
